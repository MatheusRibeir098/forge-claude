#!/usr/bin/env bash
# PreToolUse (Write|Edit): impõe o invariante "o Forge/orquestrador não escreve
# código de produto". Subagentes (dev/tester) escrevem livremente.
#
# Distinção verificada na CLI 2.1.222 e 2.1.260: o payload
# do PreToolUse inclui
# "agent_type"/"agent_id" QUANDO a chamada vem de um subagente; na sessão-raiz esses campos
# não existem. Logo: sem agent_type => é o orquestrador => aplicar a allowlist de caminhos.
#
# A decisão de caminho (modos fábrica/repo atual, allowlist, exceção do /forge:setup) vive em
# lib/decisao_escrita.py e é COMPARTILHADA com deny-orchestrator-bash-writes.py (escrita via
# Bash), para que as duas regras nunca divirjam. Resumo dos modos, detectados pela raiz do
# projeto (cwd do payload, senão CLAUDE_PROJECT_DIR):
#   fábrica     — raiz tem `projects/` E `templates/prompt.template.md` (layout do
#                 Forge como fábrica standalone). Allowlist igual à de sempre:
#                 */.forge/*, */prompt.md, */templates/*, *.md, *.markdown — em qualquer
#                 lugar do repo.
#   repo atual  — qualquer outro caso, ou seja, o Forge (como plugin) rodando dentro do
#                 repositório de trabalho de alguém. O orquestrador só pode escrever em
#                 `.forge/**` NA RAIZ do repo, em `*.md`/`*.markdown` e em `prompt.md`.
#   Nos dois modos também é livre: tudo FORA da raiz do projeto (scratchpad, /tmp, ~/.claude);
#   artefatos *.log/*.patch/*.diff/*.out/*.txt (exceto requirements*.txt); e os arquivos de
#   configuração do /forge:setup (.gitignore, .claude/settings.json, .claude/settings.local.json,
#   projects/.gitkeep, templates/.npmrc), só na raiz do projeto.
#                 Não pode escrever código-fonte.
#
# O payload chega pelo stdin e é repassado ao Python por variável de ambiente.

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
payload=$(cat)

FORGE_HOOK_LIB="$HOOK_DIR/lib" FORGE_HOOK_PAYLOAD="$payload" python3 -c '
import json, os, sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.environ["FORGE_HOOK_LIB"])
from decisao_escrita import avalia_caminho, raiz_do_payload

try:
    d = json.loads(os.environ.get("FORGE_HOOK_PAYLOAD", ""))
except Exception:
    sys.exit(0)  # payload ilegível: não bloqueia

# Subagente (dev/tester): pode escrever qualquer coisa.
if d.get("agent_type"):
    sys.exit(0)

file_path = (d.get("tool_input") or {}).get("file_path") or ""
liberado, modo, permitido_desc = avalia_caminho(file_path, raiz_do_payload(d))
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
