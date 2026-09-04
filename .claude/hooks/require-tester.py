#!/usr/bin/env python3
"""PostToolUse (Agent): avisa o orquestrador que a tarefa que ele acabou de despachar
precisará do `tester`, no instante em que ele despacha o `dev`.

POR QUE ESTE LEMBRETE EXISTE: o loop dev→tester está descrito na skill `orchestrator`, que é
carregada sob demanda — e foi carregada 6 vezes em 38 sessões (16%). Sem ela o orquestrador
improvisa o ciclo, e o `tester` é o passo que cai: 4 invocações contra 180 do `dev`. Uma
regra a mais no prompt não resolve o que 84% das sessões nunca leram.

POR QUE LÊ O BRIEFING, E NÃO O RETORNO DO DEV — três coisas verificadas com payload real na
CLI 2.1.260, todas contra o que a intuição sugeria:
  1. A invocação de subagente é ASSÍNCRONA. O PostToolUse do `Agent` dispara no LANÇAMENTO
     (`tool_response` = {"isAsync": true, "status": "async_launched"}), então o retorno do
     `dev` não passa por aqui.
  2. O retorno existe em `SubagentStop.last_assistant_message` — mas o `additionalContext`
     emitido no SubagentStop NÃO é injetado no orquestrador (testado: ele respondeu "NADA
     RECEBIDO"). Além disso o SubagentStop disparou 9 vezes para uma única invocação.
  3. Logo, o único ponto com injeção que chega ao orquestrador é este. Como aqui só existe a
     ENTRADA, decidimos pelo briefing: se a tarefa despachada menciona arquivo observável
     (UI/rota) ou fala de tela/componente/endpoint, o lembrete vale.

Fica em silêncio quando o briefing não tem nada observável. Das 180 invocações de `dev` nos
transcripts, apenas 36 tocaram UI ou rota/API; nas outras 144 (Python, script, config) o
`tester` não se aplica e o lembrete seria só ruído.
"""
import json
import re
import sys

ARQ_UI = re.compile(r"[\w./-]+\.(?:tsx|jsx|vue|svelte|html|css|scss)\b", re.I)
ARQ_API = re.compile(
    r"[\w./-]*(?:routes?|api|endpoints?|server|controllers?)[\w./-]*"
    r"\.(?:ts|js|py|go|rb)\b", re.I)
# rede de segurança para briefing que descreve sem nomear arquivo
PALAVRAS = re.compile(
    r"\b(?:componente|tela|p[áa]gina|layout|rota|endpoint|formul[áa]rio|modal|dashboard"
    r"|responsiv[oa]|dark\s*mode|bot[ãa]o)\b", re.I)


def main() -> int:
    try:
        d = json.load(sys.stdin)
    except Exception:
        return 0  # payload ilegível nunca atrapalha o trabalho

    # Só a sessão-raiz orquestra; um subagente que despache outro não é o nosso caso.
    if d.get("agent_id"):
        return 0

    inp = d.get("tool_input") or {}
    if (inp.get("subagent_type") or "") != "dev":
        return 0

    briefing = " ".join(str(inp.get(k) or "") for k in ("prompt", "description"))
    if not briefing.strip():
        return 0

    brutos = set(ARQ_UI.findall(briefing)) | {m.group(0) for m in ARQ_API.finditer(briefing)}

    # Normaliza: o mesmo arquivo aparece como caminho absoluto, relativo e nome puro.
    # Mantemos um por nome, preferindo a forma mais curta.
    por_nome: dict[str, str] = {}
    for caminho in brutos:
        nome = caminho.rsplit("/", 1)[-1]
        if nome not in por_nome or len(caminho) < len(por_nome[nome]):
            por_nome[nome] = caminho
    achados = sorted(por_nome.values(), key=lambda c: (c.count("/"), c))

    if achados:
        alvo = f"tocando {', '.join(achados[:5])}" + (" …" if len(achados) > 5 else "")
    elif PALAVRAS.search(briefing):
        alvo = "com algo observável na descrição"
    else:
        return 0

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": (
            f"[validação pendente] Você despachou um `dev` {alvo}. Quando ele retornar, "
            "invoque o `tester` ANTES de marcar a tarefa como concluída em tasks.md — passe "
            "os `comandos_para_subir` que o `dev` devolver, diga quais telas/rotas validar e "
            "o teto de prints (máx. 5). O `dev` está bloqueado por hook de subir servidor e "
            "rodar E2E, então sem o `tester` esta tarefa não é validada por ninguém. Se "
            "houver outro `dev` liberado, dispare-o na mesma mensagem do `tester` para "
            "rodarem em paralelo."
        ),
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
