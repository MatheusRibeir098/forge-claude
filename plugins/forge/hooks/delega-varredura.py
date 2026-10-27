#!/usr/bin/env python3
"""PostToolUse (Read|Grep|Glob|Bash|WebFetch|WebSearch|Edit|Write|Agent|mcp__.*, sessão-raiz): conta
leituras CONSECUTIVAS do orquestrador e, ao atingir o limiar, injeta um lembrete sugerindo
delegar a varredura ao `scout` — em vez de continuar acumulando arquivo no contexto dele.

POR QUE ESTE HOOK EXISTE
`subagent-turn-budget.sh` põe teto em `dev`/`tester`/`scout`/etc., mas ignora a sessão-raiz de
propósito: o comentário lá diz que "seu limite é a compactação da própria sessão". Isso não
basta como freio: o turno da sessão principal tende a custar mais que o de um subagente,
porque o contexto dela acumula tudo, e o orquestrador pode gastar a maior parte das chamadas
lendo (Read/Grep/Glob/Bash) em vez de delegar.

A causa é a mesma documentada nos outros hooks deste diretório: o que o orquestrador lê entra
no contexto DELE, que é reenviado inteiro em todo turno seguinte e nunca é podado. A mesma
varredura feita pelo subagente `scout` custa uma fração disso e morre junto com ele quando termina.

O QUE CONTA COMO LEITURA (e o que zera)
`Read`, `Grep`, `Glob`, `Bash`, `WebFetch`, `WebSearch` e TODA ferramenta MCP (nome começando
por `mcp__`, ex.: Chrome, Drive) incrementam a corrida. Qualquer outra
ferramenta — `Edit`, `Write`, `Agent`, `Task` etc. — ZERA o contador: a corrida é de leitura
CONSECUTIVA, e editar ou despachar um subagente já é o comportamento que este hook quer
incentivar, não algo a penalizar.

O LIMIAR PADRÃO É 8
Na exploração normal a sessão-raiz faz poucas leituras seguidas; chegar a 8 sem editar nem
delegar é sinal de varredura. Baixo o bastante para pegar corrida longa de
verdade, alto o bastante para não incomodar a exploração normal.
Não mude o padrão sem evidência do seu uso — ajuste por `FORGE_LEITURA_LIMIAR` se precisar experimentar.

COOLDOWN OBRIGATÓRIO — isso não é hipótese, é um risco concreto de projeto
Ao injetar o lembrete, o contador VOLTA A ZERO. Injetar de novo a cada leitura seguinte
transformaria o aviso em ruído: é o mesmo risco do lembrete do
`require-tester.py` (ver o próprio `require-tester.py`) — a adesão cai quando boa parte
dos disparos é falso positivo. Um lembrete que fala demais é pior que nenhum. Por isso, depois de injetar,
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
NOME_ARQUIVO_MCP = "consecutivas_mcp"  # 1 se a corrida atual já teve alguma chamada MCP
PREFIXO_MCP = "mcp__"


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


def _eh_leitura(tool_name: str) -> bool:
    return tool_name in FERRAMENTAS_DE_LEITURA or tool_name.startswith(PREFIXO_MCP)


def _mensagem(n: int, limiar: int, com_mcp: bool = False) -> str:
    dica_mcp = (
        " Entre elas há chamadas MCP (navegador/Drive etc.): trabalho operacional de "
        "navegador deve ir para o `tester` ou o `scout`, não ser conduzido da sessão "
        "principal."
    ) if com_mcp else ""
    return (
        f"[leitura consecutiva] {n} chamadas de leitura seguidas na sessão principal "
        "(Read/Grep/Glob/Bash/WebFetch/WebSearch/mcp__*), sem nenhuma edição ou despacho de "
        "subagente no meio. Tudo que você lê aqui fica no SEU contexto e é reenviado por "
        "inteiro em TODO turno seguinte — é o maior gasto do Forge. A mesma varredura feita "
        "por um `scout` custa bem menos e é descartada quando ele termina. Considere "
        "despachar um `scout` com a pergunta específica em vez de abrir mais um arquivo "
        "você mesmo. Não vale a pena para leitura pontual de 1 ou 2 arquivos que você já "
        f"sabe quais são — este aviso só dispara a partir de {limiar} leituras seguidas."
        + dica_mcp
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

    flag_mcp = estado / NOME_ARQUIVO_MCP

    if not _eh_leitura(tool_name):
        # Edit, Write, Agent, Task ou qualquer outra ferramenta: corrida quebrada.
        _gravar_contador(contador, 0)
        _gravar_contador(flag_mcp, 0)
        return 0

    limiar = _env_int("FORGE_LEITURA_LIMIAR", 8)
    n = _ler_contador(contador) + 1
    if tool_name.startswith(PREFIXO_MCP):
        _gravar_contador(flag_mcp, 1)
    com_mcp = _ler_contador(flag_mcp) == 1

    if n >= limiar:
        # Limiar atingido: injeta o lembrete e zera o contador (cooldown).
        _gravar_contador(contador, 0)
        _gravar_contador(flag_mcp, 0)
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": _mensagem(n, limiar, com_mcp),
        }}))
        return 0

    _gravar_contador(contador, n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
