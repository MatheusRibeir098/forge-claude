#!/usr/bin/env bash
# Encadeia o `rtk hook claude` também para a sessão-raiz (o orquestrador conversando direto
# com o usuário) — subagent-turn-budget.sh já faz isso para dev/tester/scout/etc, mas ignora
# de propósito quem não tem agent_id no payload (ver o comentário lá). Este hook cobre só essa
# lacuna; não repita a delegação para subagentes aqui, ou dois hooks disputariam o mesmo
# veredito de permissão no mesmo evento Bash.

payload=$(cat)
RTK_BIN="${FORGE_RTK_BIN:-/home/math3us/.local/bin/rtk}"

agent_id=$(FORGE_HOOK_PAYLOAD="$payload" python3 -c '
import json, os
try: d = json.loads(os.environ["FORGE_HOOK_PAYLOAD"])
except Exception: raise SystemExit
print(d.get("agent_id") or "")
')

# Tem agent_id => subagente, já tratado em subagent-turn-budget.sh.
[ -n "$agent_id" ] && exit 0

source "$(dirname "${BASH_SOURCE[0]}")/lib/rtk-bash-delegate.sh"
rtk_delegate_if_allowed "$payload" "$RTK_BIN"
exit 0
