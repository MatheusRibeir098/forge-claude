#!/usr/bin/env bash
# Delegação de comandos Bash de leitura ao `rtk hook claude` — compartilhada entre o hook de
# subagentes (subagent-turn-budget.sh) e o hook da sessão-raiz (rtk-root.sh), para não duplicar
# a allowlist. Ver o comentário no topo de subagent-turn-budget.sh para o porquê da restrição:
# a reescrita troca o comando ANTES da checagem de `permissions`, então delegar tudo faria
# `git push` escapar da regra `ask` e `cat`/`ls`/`find` saírem da allowlist.
RTK_OK='^((uv[[:space:]]+run[[:space:]]+|pnpm[[:space:]]+exec[[:space:]]+|npx[[:space:]]+|python3?[[:space:]]+-m[[:space:]]+)?(jest|vitest|pytest|playwright|tsc|ruff|eslint)|git[[:space:]]+(status|diff|show|branch)|find|ls|tree)([[:space:]]|$)'

# Uso: rtk_delegate_if_allowed "$payload" "$RTK_BIN"
# Espera payload de um evento PreToolUse/Bash já confirmado pelo chamador.
rtk_delegate_if_allowed() {
    local payload="$1" rtk_bin="$2"
    [ -x "$rtk_bin" ] || return 0
    local cmd
    cmd=$(FORGE_HOOK_PAYLOAD="$payload" python3 -c '
import json, os
try: d = json.loads(os.environ["FORGE_HOOK_PAYLOAD"])
except Exception: raise SystemExit
print(((d.get("tool_input") or {}).get("command") or "").strip())
')
    if printf '%s' "$cmd" | grep -Eq "$RTK_OK"; then
        printf '%s' "$payload" | "$rtk_bin" hook claude 2>/dev/null || true
    fi
}
