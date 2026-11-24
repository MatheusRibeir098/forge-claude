#!/usr/bin/env bash
# PreToolUse (Write|Edit|NotebookEdit): impõe o invariante "o Forge/orquestrador não escreve
# código de produto". Subagentes (dev/tester) escrevem livremente, exceto no modo "projeto da
# fábrica" (abaixo), onde só a contenção os alcança.
#
# Distinção medida na CLI 2.1.331: o payload do PreToolUse traz "agent_id" (e "agent_type")
# QUANDO a chamada vem de um subagente, em qualquer profundidade; a sessão-raiz não traz nenhum
# dos dois. Com `claude --agent X` a raiz traz "agent_type" SEM "agent_id" — por isso o critério
# é "agent_id": sem ele é o orquestrador (raiz) => aplicar a allowlist de caminhos.
#
# A decisão de caminho (modos, allowlist, exceção do /forge:setup, contenção) vive em
# lib/decisao_escrita.py e é COMPARTILHADA com deny-orchestrator-bash-writes.py (escrita via
# Bash), para que as duas regras nunca divirjam. Resumo dos TRÊS modos, detectados pela raiz da
# sessão (cwd do payload, senão CLAUDE_PROJECT_DIR):
#   fábrica     — raiz tem `projects/` E `templates/prompt.template.md` (layout do
#                 Forge como fábrica standalone). Allowlist igual à de sempre:
#                 */.forge/*, */prompt.md, */templates/*, *.md, *.markdown — em qualquer
#                 lugar do repo.
#   projeto da fábrica
#               — a raiz (ou um ancestral, P) está em `<fábrica>/projects/<nome>`: sessão aberta
#                 direto no projeto. Contenção em P. Orquestrador: dentro de P, a allowlist do
#                 "repo atual" com P como raiz; fora de P, NEGADO (qualquer extensão), salvo /tmp,
#                 $TMPDIR e ~/.claude*. Subagente: livre dentro de P; fora de P, mesma regra.
#   repo atual  — qualquer outro caso, ou seja, o Forge (como plugin) rodando dentro do
#                 repositório de trabalho de alguém. O orquestrador só pode escrever em
#                 `.forge/**` NA RAIZ do repo, em `*.md`/`*.markdown` e em `prompt.md`.
#   Nos modos fábrica e repo atual também é livre: tudo FORA da raiz do projeto (scratchpad,
#   /tmp, ~/.claude); artefatos *.log/*.patch/*.diff/*.out/*.txt (exceto requirements*.txt); e os
#   arquivos de configuração do /forge:setup (.gitignore, .claude/settings.json,
#   .claude/settings.local.json, projects/.gitkeep, templates/.npmrc), só na raiz do projeto.
#                 Não pode escrever código-fonte.
#
# O payload chega pelo stdin e é repassado ao Python por variável de ambiente.

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
payload=$(cat)

FORGE_HOOK_LIB="$HOOK_DIR/lib" FORGE_HOOK_PAYLOAD="$payload" python3 -c '
import json, os, sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.environ["FORGE_HOOK_LIB"])
from decisao_escrita import (MOTIVO_CONTENCAO, avalia_escrita, mensagem_contencao,
                              raiz_do_payload)

try:
    d = json.loads(os.environ.get("FORGE_HOOK_PAYLOAD", ""))
except Exception:
    sys.exit(0)  # payload ilegível: não bloqueia

# Subagente (dev/tester): livre, exceto na contenção do modo projeto da fábrica.
# NotebookEdit traz o alvo em notebook_path; Write/Edit, em file_path.
tool_input = d.get("tool_input") or {}
file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
decisao = avalia_escrita(file_path, raiz_do_payload(d), subagente=bool(d.get("agent_id")))
if decisao.liberado:
    sys.exit(0)

if decisao.motivo == MOTIVO_CONTENCAO:
    reason = mensagem_contencao(decisao, file_path)
else:
    reason = (
        f"O Forge (orquestrador) não escreve código de produto. Modo detectado: {decisao.modo}. "
        f"Permitido neste modo: {decisao.permitido_desc}. Monte um briefing e invoque o subagente "
        "dev via ferramenta Agent."
    )
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": reason,
}}))
sys.exit(0)
'
