#!/usr/bin/env python3
"""Largura de despacho: cutuca o orquestrador quando ele despacha agentes um a um, em vez de
planejar quantos cabem e mandá-los juntos. NUNCA bloqueia: só injeta `additionalContext`
(jamais `permissionDecision`, `decision: block` ou `updatedInput`). Qualquer exceção ou
payload ilegível termina em `exit 0` calado. Só stdlib.

DOIS EVENTOS (o script despacha por `hook_event_name`)

  PostToolUse(Agent), só na raiz (payload sem `agent_id`)
      Lê o `transcript_path`, agrupa as linhas `type: assistant` por `message.id` e conta os
      blocos `tool_use` com `name == "Agent"` na mensagem que fez a chamada (a que contém o
      `tool_use_id` do payload; sem ele, a última). Cutuca só quando:
        - a contagem é exatamente 1 (um agente sozinho na mensagem);
        - o `subagent_type` é `forge:*`, `general-purpose` ou `Explore`;
        - é a primeira vez para esse `message.id` (dedup em `largura-vistos.json`).
      Lançamento em lote (2 ou mais `Agent` na mesma mensagem) não cutuca.

  UserPromptSubmit
      Se o texto do usuário pede agentes (scout, invoque, subagente, agentes, paralelo), grava a
      flag `pediu_agentes` da sessão e devolve a instrução de despachar 3 ou mais scouts. Se
      não pede, apaga a flag. O `delega-varredura.py` lê a flag e baixa o limiar de leituras
      seguidas da raiz de 8 para 3.

ESTADO — mesmo diretório do `delega-varredura.py`, para os dois enxergarem a flag:
`FORGE_STATE_DIR` explícito (como está) > `XDG_RUNTIME_DIR` > `TMPDIR` > `/tmp`, sob
`forge/leituras/<session_id>`.
"""
import json
import os
import pathlib
import re
import sys

NOME_FLAG = "pediu_agentes"
NOME_VISTOS = "largura-vistos.json"
TETO_VISTOS = 200
LIMITE_LEITURA_TRANSCRIPT = 1024 * 1024  # só o final do JSONL: a mensagem que importa é a última
TIPOS_COM_PLANO = frozenset({"general-purpose", "Explore"})
PREFIXO_FORGE = "forge:"

RE_SESSAO_INVALIDA = re.compile(r"[^A-Za-z0-9_-]")
RE_PEDIDO_DE_AGENTES = re.compile(
    r"\bscouts?\b|\binvo(?:ca|que|ke)|\bsub-?agentes?\b|\bagentes\b|\bparalel", re.I)

TEXTO_AGENTE_SOZINHO = (
    "Saiu 1 agente sozinho. Há outras frentes ou tarefas prontas? Se sim, despache juntas na "
    "próxima mensagem (teto 12: scouts 8, devs 6, testers de contrato 6, navegador 1). Se é "
    "dependência real, siga."
)
TEXTO_PEDIU_AGENTES = (
    "O usuário pediu agentes: faça o plano de largura e despache 3 ou mais scouts (um por "
    "frente) antes de ler você mesmo."
)


def _diretorio_de_estado(session_id) -> pathlib.Path:
    explicito = os.environ.get("FORGE_STATE_DIR")
    if explicito:
        return pathlib.Path(explicito)
    base = os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("TMPDIR") or "/tmp"
    sessao = RE_SESSAO_INVALIDA.sub("", session_id)[:120] if isinstance(session_id, str) else ""
    corpo = pathlib.Path(base) / "forge" / "leituras"
    return corpo / sessao if sessao else corpo


def _emitir(evento: str, texto: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": evento,
        "additionalContext": texto,
    }}, ensure_ascii=False))


# --- UserPromptSubmit --------------------------------------------------------------------

def _tratar_prompt(d: dict) -> int:
    prompt = d.get("prompt")
    pasta = _diretorio_de_estado(d.get("session_id"))
    flag = pasta / NOME_FLAG
    if not isinstance(prompt, str) or not RE_PEDIDO_DE_AGENTES.search(prompt):
        flag.unlink(missing_ok=True)
        return 0
    pasta.mkdir(parents=True, exist_ok=True)
    flag.write_text("1", encoding="utf-8")
    _emitir("UserPromptSubmit", TEXTO_PEDIU_AGENTES)
    return 0


# --- PostToolUse(Agent) ------------------------------------------------------------------

def _linhas_finais(caminho: str) -> list:
    """Linhas do final do transcript; descarta a primeira quando o corte caiu no meio dela."""
    with open(os.path.expanduser(caminho), "rb") as fh:
        fh.seek(0, os.SEEK_END)
        tamanho = fh.tell()
        inicio = max(0, tamanho - LIMITE_LEITURA_TRANSCRIPT)
        fh.seek(inicio)
        linhas = fh.read().decode("utf-8", errors="replace").splitlines()
    return linhas[1:] if inicio > 0 else linhas


def _mensagens_do_assistente(linhas: list) -> dict:
    """`message.id` -> blocos de conteúdo, na ordem do transcript (um id por mensagem)."""
    grupos = {}
    for linha in linhas:
        try:
            registro = json.loads(linha)
        except ValueError:
            continue
        if not isinstance(registro, dict) or registro.get("type") != "assistant":
            continue
        mensagem = registro.get("message")
        if not isinstance(mensagem, dict):
            continue
        chave = mensagem.get("id") or registro.get("uuid")
        conteudo = mensagem.get("content")
        if isinstance(chave, str) and isinstance(conteudo, list):
            grupos.setdefault(chave, []).extend(b for b in conteudo if isinstance(b, dict))
    return grupos


def _chamadas_agent(blocos: list) -> list:
    """Inputs dos blocos `Agent`, sem repetir o mesmo `tool_use` visto em mais de uma linha."""
    vistos, entradas = set(), []
    for bloco in blocos:
        if bloco.get("type") != "tool_use" or bloco.get("name") != "Agent":
            continue
        ident = bloco.get("id")
        if ident in vistos:
            continue
        vistos.add(ident)
        entradas.append(bloco.get("input") if isinstance(bloco.get("input"), dict) else {})
    return entradas


def _mensagem_da_chamada(grupos: dict, tool_use_id):
    """(message.id, blocos) da mensagem que contém `tool_use_id`; sem ele, a última."""
    if isinstance(tool_use_id, str) and tool_use_id:
        for chave, blocos in grupos.items():
            if any(b.get("id") == tool_use_id for b in blocos):
                return chave, blocos
    if not grupos:
        return None, []
    chave = list(grupos)[-1]
    return chave, grupos[chave]


def _tipo_com_plano(subagent_type) -> bool:
    if not isinstance(subagent_type, str):
        return False
    return subagent_type.startswith(PREFIXO_FORGE) or subagent_type in TIPOS_COM_PLANO


def _primeira_vez(pasta: pathlib.Path, message_id: str) -> bool:
    """Registra o `message.id` e diz se ele ainda não tinha cutucado."""
    arquivo = pasta / NOME_VISTOS
    try:
        vistos = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        vistos = []
    vistos = vistos if isinstance(vistos, list) else []
    if message_id in vistos:
        return False
    vistos.append(message_id)
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps(vistos[-TETO_VISTOS:]), encoding="utf-8")
    except OSError:
        return True
    return True


def _tratar_agent(d: dict) -> int:
    if d.get("agent_id") or d.get("tool_name") not in (None, "Agent"):
        return 0  # só a raiz orquestra
    caminho = d.get("transcript_path")
    if not isinstance(caminho, str) or not caminho:
        return 0
    grupos = _mensagens_do_assistente(_linhas_finais(caminho))
    message_id, blocos = _mensagem_da_chamada(grupos, d.get("tool_use_id"))
    chamadas = _chamadas_agent(blocos)
    if message_id is None or len(chamadas) != 1:
        return 0
    if not _tipo_com_plano(chamadas[0].get("subagent_type")):
        return 0
    if not _primeira_vez(_diretorio_de_estado(d.get("session_id")), message_id):
        return 0
    _emitir("PostToolUse", TEXTO_AGENTE_SOZINHO)
    return 0


# --- entrada -----------------------------------------------------------------------------

def main() -> int:
    try:
        d = json.load(sys.stdin)
        if not isinstance(d, dict):
            return 0
        evento = d.get("hook_event_name")
        if evento == "UserPromptSubmit":
            return _tratar_prompt(d) if not d.get("agent_id") else 0
        if evento == "PostToolUse":
            return _tratar_agent(d)
    except Exception:
        return 0  # um lembrete nunca pode ser o motivo de a tarefa travar
    return 0


if __name__ == "__main__":
    sys.exit(main())
