#!/usr/bin/env bash
# PreToolUse (Write|Edit): impõe o invariante "o Forge/orquestrador não escreve
# código de produto". Subagentes (dev/tester) escrevem livremente.
#
# Distinção verificada empiricamente na CLI 2.1.222, reconfirmada na 2.1.260: o payload
# do PreToolUse inclui
# "agent_type"/"agent_id" QUANDO a chamada vem de um subagente; na sessão-raiz esses campos
# não existem. Logo: sem agent_type => é o orquestrador => aplicar a allowlist de caminhos.
#
# DOIS MODOS, detectados pela raiz do projeto (cwd do payload, senão CLAUDE_PROJECT_DIR):
#   fábrica     — raiz tem `projects/` E `templates/prompt.template.md` (layout histórico
#                 do Forge como fábrica standalone). Allowlist igual à de sempre:
#                 */.forge/*, */prompt.md, */templates/*, *.md, *.markdown — em qualquer
#                 lugar do repo.
#   repo atual  — qualquer outro caso, ou seja, o Forge (como plugin) rodando dentro do
#                 repositório de trabalho de alguém. O orquestrador só pode escrever em
#                 `.forge/**` NA RAIZ do repo, em `*.md`/`*.markdown`, e em `prompt.md`.
#                 Não pode escrever código-fonte.
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

# Raiz do projeto: cwd do payload (mais confiável — é onde a sessão realmente está rodando),
# senão CLAUDE_PROJECT_DIR, senão o diretório de trabalho do próprio hook.
root = d.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
root = os.path.abspath(root)

is_fabrica = (
    os.path.isdir(os.path.join(root, "projects"))
    and os.path.isfile(os.path.join(root, "templates", "prompt.template.md"))
)

if is_fabrica:
    modo = "fábrica"
    permitido_desc = (
        "prompt.md, .forge/*, templates/*, *.md/*.markdown (em qualquer lugar do repo — "
        "detectado por projects/ + templates/prompt.template.md na raiz)"
    )
    allow = ["*/.forge/*", "*/prompt.md", "*/templates/*", "*.md", "*.markdown"]
    liberado = any(fnmatch.fnmatch(file_path, g) for g in allow)
else:
    modo = "repo atual"
    permitido_desc = (
        "escrever em .forge/** na raiz do repo, em *.md/*.markdown, e em prompt.md — "
        "nunca em código-fonte"
    )
    abs_file = file_path if os.path.isabs(file_path) else os.path.join(root, file_path)
    abs_file = os.path.normpath(abs_file)
    forge_dir = os.path.normpath(os.path.join(root, ".forge"))
    dentro_do_forge = abs_file == forge_dir or abs_file.startswith(forge_dir + os.sep)
    eh_markdown = fnmatch.fnmatch(file_path, "*.md") or fnmatch.fnmatch(file_path, "*.markdown")
    eh_prompt = os.path.basename(file_path) == "prompt.md"
    liberado = dentro_do_forge or eh_markdown or eh_prompt

if liberado:
    sys.exit(0)

reason = (
    f"O Forge (orquestrador) não escreve código de produto. Modo detectado: {modo}. "
    f"Permitido neste modo: {permitido_desc}. Monte um briefing e invoque o subagente dev "
    "via ferramenta Agent."
)
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": reason,
}}))
sys.exit(0)
'
