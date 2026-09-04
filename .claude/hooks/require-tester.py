#!/usr/bin/env python3
"""PostToolUse (Agent): lembra o orquestrador de validar, no instante em que o `dev` retorna.

POR QUE AQUI: o loop dev→tester está descrito na skill `orchestrator`, que é carregada sob
demanda — e foi carregada 6 vezes em 38 sessões (16%). Sem ela o orquestrador improvisa o
ciclo, e o `tester` é o passo que cai: 4 invocações contra 180 do `dev`. Uma regra a mais no
prompt não resolve o que 84% das sessões nunca leram; então o lembrete é injetado no único
momento em que ele é acionável — quando o retorno do `dev` chega.

Só dispara quando há algo observável para testar. Das 180 invocações de `dev`, apenas 36
tocaram UI ou rota/API; nas outras 144 (Python, script, config) o `tester` não se aplica e um
lembrete seria só ruído.
"""
import json
import re
import sys

UI = re.compile(r"[\w./-]+\.(?:tsx|jsx|vue|svelte|html|css|scss)\b", re.I)
API = re.compile(
    r"[\w./-]*(?:routes?|api|endpoints?|server|controllers?)[\w./-]*"
    r"\.(?:ts|js|py|go|rb)\b", re.I)
ABERTO = re.compile(r'"status"\s*:\s*"(?:BLOQUEADO|PARCIAL)"', re.I)


def main() -> int:
    try:
        d = json.load(sys.stdin)
    except Exception:
        return 0  # payload ilegível nunca atrapalha o trabalho

    # Só a sessão-raiz orquestra; um subagente que chame outro não é o nosso caso.
    if d.get("agent_id"):
        return 0
    if ((d.get("tool_input") or {}).get("subagent_type") or "") != "dev":
        return 0

    saida = d.get("tool_output")
    if not isinstance(saida, str):
        saida = json.dumps(saida, ensure_ascii=False)

    # Trabalho ainda aberto: o orquestrador já tem o que fazer antes de pensar em validação.
    if ABERTO.search(saida):
        return 0

    achados = sorted(set(UI.findall(saida)) | {m.group(0) for m in API.finditer(saida)})
    if not achados:
        return 0

    lista = ", ".join(achados[:6]) + (" …" if len(achados) > 6 else "")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": (
            f"[validação pendente] O `dev` entregou e tocou arquivo observável ({lista}). "
            "Invoque o `tester` antes de marcar a tarefa como concluída em tasks.md — passe "
            "os `comandos_para_subir` que o `dev` devolveu, diga quais telas/rotas validar e "
            "o teto de prints (máx. 5). O `dev` está bloqueado por hook de subir servidor e "
            "rodar E2E, então sem o `tester` esta tarefa não foi validada por ninguém. Se "
            "houver outro `dev` liberado, dispare os dois na mesma mensagem para rodarem em "
            "paralelo."
        ),
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
