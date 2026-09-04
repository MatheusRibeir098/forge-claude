#!/usr/bin/env bash
# PreToolUse (Write|Edit): impõe o invariante "o Forge/orquestrador não escreve
# código de produto". Subagentes (dev/tester) escrevem livremente.
#
# Distinção verificada empiricamente na CLI 2.1.222, reconfirmada na 2.1.260: o payload
# do PreToolUse inclui
# "agent_type"/"agent_id" QUANDO a chamada vem de um subagente; na sessão-raiz esses campos
# não existem. Logo: sem agent_type => é o orquestrador => aplicar a allowlist de caminhos.
#
# A decisão é feita em Python (evita bugs de parsing de shell). O payload chega pelo stdin e
# é repassado ao Python por variável de ambiente.

payload=$(cat)

FORGE_HOOK_PAYLOAD="$payload" python3 -c '
import json, os, sys, fnmatch

try:
    d = json.loads(os.environ.get("FORGE_HOOK_PAYLOAD", ""))
except Exception:
    sys.exit(0)  # payload ilegível: não bloqueia

agent_type = d.get("agent_type") or ""
file_path = (d.get("tool_input") or {}).get("file_path") or ""

# Subagente (dev/tester): pode escrever qualquer coisa.
if agent_type:
    sys.exit(0)

# Sessão-raiz (orquestrador): só arquivos de controle e documentação.
allow = ["*/.forge/*", "*/prompt.md", "*/templates/*", "*.md", "*.markdown"]
if any(fnmatch.fnmatch(file_path, g) for g in allow):
    sys.exit(0)

reason = ("O Forge (orquestrador) não escreve código de produto. Monte um briefing e invoque "
          "o subagente dev via Task tool. (Permitidos ao orquestrador: prompt.md, .forge/*, "
          "templates/*, *.md)")
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": reason,
}}))
sys.exit(0)
'
