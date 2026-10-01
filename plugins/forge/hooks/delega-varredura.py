#!/usr/bin/env python3
"""PostToolUse (Read|Grep|Glob|Bash|WebFetch|WebSearch|Edit|Write|Agent, sessão-raiz): conta
leituras CONSECUTIVAS do orquestrador e, ao passar do limiar, injeta um lembrete sugerindo
delegar a varredura ao `scout` — em vez de continuar acumulando arquivo no contexto dele.

POR QUE ESTE HOOK EXISTE — a medição que faltava
`subagent-turn-budget.sh` põe teto em `dev`/`tester`/`scout`/etc., mas ignora a sessão-raiz de
propósito: o comentário lá diz que "seu limite é a compactação da própria sessão". A medição
corrigida mostrou que isso não segura:

    custo por turno na sessão principal:  US$ 0,1598
    custo por turno em subagente:         US$ 0,0456   (sessão principal é 3,5x mais cara)
    sessão principal: 26% dos turnos, 55% da conta
    orquestrador: 326 chamadas de Read/Grep/Glob/Bash contra só 41 invocações de subagente
                  no mesmo período — 63% do que ele faz é ler, não delegar.

A causa é a mesma documentada nos outros hooks deste diretório: o que o orquestrador lê entra
no contexto DELE, que é reenviado inteiro em todo turno seguinte e nunca é podado. A mesma
varredura feita pelo subagente `scout` custa ~US$ 0,08 e morre junto com ele quando termina.

O QUE CONTA COMO LEITURA (e o que zera)
`Read`, `Grep`, `Glob`, `Bash`, `WebFetch`, `WebSearch` incrementam a corrida. Qualquer outra
ferramenta — `Edit`, `Write`, `Agent`, `Task` etc. — ZERA o contador: a corrida é de leitura
CONSECUTIVA, e editar ou despachar um subagente já é o comportamento que este hook quer
incentivar, não algo a penalizar.

O LIMIAR PADRÃO É 8 E NÃO FOI CHUTADO
Medição das corridas de leitura consecutiva na sessão-raiz (98 corridas observadas):
mediana 2, p75 5, p90 9, máximo 23. Um limiar de 8 dispara em 16 de 98 corridas — cerca de
1 vez a cada 2 sessões. Baixo o bastante para pegar corrida longa de verdade, alto o
bastante para não incomodar a exploração normal (mediana 2, p75 5 nunca tocam o limiar).
NÃO MUDE O PADRÃO sem remedir — ajuste por `FORGE_LEITURA_LIMIAR` se precisar experimentar.

COOLDOWN OBRIGATÓRIO — isso não é hipótese, já aconteceu neste plugin
Ao injetar o lembrete, o contador VOLTA A ZERO. Injetar de novo a cada leitura seguinte
transformaria o aviso em ruído: é exatamente o que já aconteceu com o lembrete do
`require-tester.py` na versão anterior (ver o cabeçalho de `subagent-turn-budget.sh` e o
próprio `require-tester.py`) — a adesão caiu de 100% para 0% porque 44 de 87 disparos eram
falso positivo. Um lembrete que fala demais é pior que nenhum. Por isso, depois de injetar,
é preciso ACUMULAR OUTRA corrida inteira de leituras consecutivas para disparar de novo.

ESTADO — mesmo esquema do `subagent-turn-budget.sh` (leia lá antes de mexer aqui)
Preferência: `FORGE_STATE_DIR` explícito (usado como está, sem subpasta) > `XDG_RUNTIME_DIR`
> `TMPDIR` > `/tmp`, e quando nenhum `FORGE_STATE_DIR` é dado, sob subcaminho próprio
(`forge/leituras`) separado por `session_id` quando o payload traz um — sessões concorrentes
não disputam o mesmo contador. Nunca escreve dentro do repositório de quem instalou o
plugin. Mesma higiene do outro hook: ao tocar o diretório de estado, apaga arquivo com mais
de 1 dia — contador de sessão encerrada não interessa.

ESTE HOOK NUNCA BLOQUEIA. Só injeta `additionalContext` — jamais `permissionDecision`.
Payload ilegível, sem `tool_name`, ou qualquer erro inesperado: `exit 0` calado. Um hook de
lembrete não pode ser o motivo de uma tarefa travar.

"""
import json
import os
import re
import sys
import time
import pathlib

# Ferramentas que contam como leitura para efeito da corrida consecutiva.
FERRAMENTAS_DE_LEITURA = frozenset({
    "Read", "Grep", "Glob", "Bash", "WebFetch", "WebSearch",
})

RE_SESSAO_INVALIDA = re.compile(r"[^A-Za-z0-9_-]")

NOME_ARQUIVO_CONTADOR = "consecutivas"


def _env_int(nome: str, padrao: int) -> int:
    try:
        valor = int(os.environ.get(nome, ""))
        return valor if valor > 0 else padrao
    except Exception:
        return padrao


def _sessao_sanitizada(session_id) -> str:
    if not isinstance(session_id, str):
        return ""
    return RE_SESSAO_INVALIDA.sub("", session_id)[:120]


def _diretorio_de_estado(session_id: str) -> pathlib.Path:
    explicito = os.environ.get("FORGE_STATE_DIR")
    if explicito:
        return pathlib.Path(explicito)
    base = os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("TMPDIR") or "/tmp"
    if session_id:
        return pathlib.Path(base) / "forge" / "leituras" / session_id
    return pathlib.Path(base) / "forge" / "leituras"


def _ler_contador(caminho: pathlib.Path) -> int:
    try:
        return int(caminho.read_text().strip())
    except Exception:
        return 0


def _gravar_contador(caminho: pathlib.Path, valor: int) -> None:
    try:
        caminho.write_text(str(valor))
    except Exception:
        pass  # não conseguir persistir não pode travar o hook


def _mensagem(n: int, limiar: int) -> str:
    return (
        f"[leitura consecutiva] {n} chamadas de leitura seguidas na sessão principal "
        "(Read/Grep/Glob/Bash/WebFetch/WebSearch), sem nenhuma edição ou despacho de "
        "subagente no meio. Tudo que você lê aqui fica no SEU contexto e é reenviado por "
        "inteiro em TODO turno seguinte — é o maior gasto do Forge. A mesma varredura feita "
        "por um `scout` custa ~US$ 0,08 e é descartada quando ele termina. Considere "
        "despachar um `scout` com a pergunta específica em vez de abrir mais um arquivo "
        "você mesmo. Não vale a pena para leitura pontual de 1 ou 2 arquivos que você já "
        f"sabe quais são — este aviso só dispara a partir de {limiar} leituras seguidas."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # payload ilegível nunca atrapalha o trabalho

    if not isinstance(payload, dict):
        return 0

    # Subagente já tem teto próprio (subagent-turn-budget.sh). Este hook é só da sessão-raiz.
    if payload.get("agent_id"):
        return 0

    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        return 0  # payload sem tool_name: não há o que classificar

    session_id = _sessao_sanitizada(payload.get("session_id"))
    estado = _diretorio_de_estado(session_id)

    try:
        estado.mkdir(parents=True, exist_ok=True)
        # higiene: contador de sessão encerrada (>1 dia) não interessa mais
        cutoff = time.time() - 86400
        for antigo in estado.iterdir():
            if antigo.is_file() and antigo.stat().st_mtime < cutoff:
                antigo.unlink(missing_ok=True)
    except Exception:
        return 0  # não conseguimos manter estado: não bloqueia nada

    contador = estado / NOME_ARQUIVO_CONTADOR

    if tool_name not in FERRAMENTAS_DE_LEITURA:
        # Edit, Write, Agent, Task ou qualquer outra ferramenta: corrida quebrada.
        _gravar_contador(contador, 0)
        return 0

    limiar = _env_int("FORGE_LEITURA_LIMIAR", 8)
    n = _ler_contador(contador) + 1

    if n >= limiar:
        # Limiar atingido: injeta o lembrete e zera o contador (cooldown).
        _gravar_contador(contador, 0)
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": _mensagem(n, limiar),
        }}))
        return 0

    _gravar_contador(contador, n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
