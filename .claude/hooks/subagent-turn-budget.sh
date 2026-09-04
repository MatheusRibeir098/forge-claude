#!/usr/bin/env bash
# Teto de turnos por invocação de subagente — a maior alavanca de custo do Forge.
#
# POR QUE: medido nos 35 transcripts do repo (ago–set/2026), o custo de uma invocação
# não cresce linear com os turnos, porque o contexto do subagente nunca é podado:
#
#   turnos na invocação │ custo médio/invocação │ custo médio POR turno
#   ────────────────────┼───────────────────────┼──────────────────────
#   1–10                │      26 mil tokens   │  10 mil
#   61–120              │    6,83 mi tokens    │  77 mil
#   121+                │   22,35 mi tokens    │ 137 mil
#
# O `dev` rodava com mediana de 76 turnos (p90 138, máx 301). Cortar em ~45 turnos
# atinge 74% das invocações e responde por ~76% da conta de subagentes.
#
# COMO: contamos chamadas de ferramenta (o payload não expõe turnos). Razão medida
# no repo: 1,73 turno por chamada de ferramenta. Logo 18 chamadas ≈ 31 turnos (aviso)
# e 26 chamadas ≈ 45 turnos (teto).
#
# Trata dois eventos com o mesmo script:
#   PostToolUse → incrementa o contador e injeta o aviso (não pode bloquear)
#   PreToolUse  → nega a ferramenta acima do teto, forçando o retorno PARCIAL
#
# E, quando LIBERA um Bash, delega ao `rtk hook claude` (Rust Token Killer), que reescreve
# o comando para a variante compacta. Por que encadeado aqui e não como hook separado: o
# hook do rtk devolve `permissionDecision: "allow"`, que competiria com o nosso `deny` no
# mesmo evento — dois vereditos, precedência indefinida. Encadeando, o veredito é um só e a
# ordem é garantida: o teto decide primeiro, o rtk só age no caminho liberado.
#
# Ganho do rtk medido no perfil de comandos DESTE repo: ~4,5% do volume de Bash (git status
# 76%, tree 98%, find 51%, build 17%; `cat`/`sed`/`grep` deram 0% sem perda de conteúdo).
# Longe dos "60-90%" anunciados — o ganho grande vem das regras de briefing (usar
# Grep/Glob/Read em vez de grep/find/cat), não do proxy.
#
# ⚠️ POR QUE A DELEGAÇÃO É RESTRITA A UMA LISTA (RTK_OK abaixo), e não "tudo que o rtk
# aceita": a reescrita acontece ANTES da checagem de permissão, então ela troca o comando
# que as regras de `permissions` vão avaliar. Deixar o rtk reescrever livremente causava
# dois problemas medidos:
#   1. `git push` virava `rtk git push` e deixava de casar com a regra `ask`
#      `Bash(git push:*)` — enfraquecendo a imposição do Invariante 2 (nunca push sozinho).
#   2. `cat`/`ls`/`find`/`pnpm install` saíam da allowlist (`Bash(cat:*)` não casa com
#      `rtk read ...`), o que geraria prompt de permissão em cada comando do loop.
# Então só delegamos comandos que (a) tiveram ganho medido, (b) são de leitura, e (c) têm a
# variante `rtk ...` explicitamente liberada em .claude/settings.json. Comando fora da lista
# segue nativo — o rtk nunca decide sozinho o que reescrever aqui.
#
# A sessão-raiz (orquestrador) não tem agent_id no payload e é ignorada aqui — seu
# limite é a compactação da própria sessão, não este contador.

payload=$(cat)
RTK_BIN="${FORGE_RTK_BIN:-/home/math3us/.local/bin/rtk}"

FORGE_HOOK_PAYLOAD="$payload" \
FORGE_STATE_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}/.claude/state/turns" \
python3 -c '
import json, os, sys, time, pathlib

try:
    d = json.loads(os.environ.get("FORGE_HOOK_PAYLOAD", ""))
except Exception:
    sys.exit(0)  # payload ilegível: nunca atrapalha o trabalho

agent_id   = d.get("agent_id") or ""
agent_type = d.get("agent_type") or ""
event      = d.get("hook_event_name") or ""

# Sem agent_id => sessão-raiz (o Forge). Não contamos o orquestrador.
if not agent_id:
    sys.exit(0)

# Tetos em CHAMADAS DE FERRAMENTA (~1,73 turno cada). Ajustáveis por env.
def env_int(name, default):
    try: return max(int(os.environ[name]), 1)
    except Exception: return default

if agent_type == "tester":
    # O tester sobe servidor, roda E2E e captura prints: precisa de mais fôlego,
    # e custa pouco (4 invocações = US$ 11 nos dados medidos).
    warn, cap = env_int("FORGE_TESTER_WARN", 30), env_int("FORGE_TESTER_CAP", 45)
elif agent_type == "scout":
    # Varredura tem muitas chamadas baratas (Glob/Grep/Read com limit), então o teto é mais
    # alto — e ele roda em haiku, o modelo mais barato do time.
    warn, cap = env_int("FORGE_SCOUT_WARN", 28), env_int("FORGE_SCOUT_CAP", 40)
else:
    warn, cap = env_int("FORGE_TURN_WARN", 18), env_int("FORGE_TURN_CAP", 26)

state = pathlib.Path(os.environ["FORGE_STATE_DIR"])
try:
    state.mkdir(parents=True, exist_ok=True)
    # higiene: contadores de invocações antigas (>1 dia) não interessam
    cutoff = time.time() - 86400
    for old in state.iterdir():
        if old.is_file() and old.stat().st_mtime < cutoff:
            old.unlink(missing_ok=True)
except Exception:
    sys.exit(0)  # não conseguimos manter estado: não bloqueia nada

counter = state / "".join(c for c in agent_id if c.isalnum() or c in "-_")[:120]

def read_count():
    try: return int(counter.read_text().strip())
    except Exception: return 0

# ---------------------------------------------------------------------------------
# Validação pesada é papel do `tester`, não do `dev`.
#
# Medido nos transcripts: o `tester` foi invocado 4 vezes contra 180 do `dev`, e 78% dos
# `dev` validavam a si mesmos. Quem valida a si mesmo rodou 84 turnos de mediana contra 32
# de quem não valida, e 20% deles estouraram 121+ turnos (US$ 334, 39% do custo do grupo).
# Além do custo, é juiz em causa própria: o design diz que o `tester` é a palavra final.
#
# A linha de corte vem da medição do que o `dev` fazia (520 chamadas de papel do tester
# contra 543 legítimas): ele MANTÉM tsc/build/lint, teste unitário e qualquer script/processo
# próprio (inclusive em background) — é o `build_ok` que ele reporta. PERDE apenas subir a
# APLICAÇÃO, browser/E2E, screenshot e curl na app.
#
# A lacuna real é menor do que parece: das 180 invocações de `dev`, só 36 tocaram UI ou
# rota/API — nas outras 144 (Python, script, config) o `tester` não se aplica. Faltavam
# ~32 validações, não 176.
if event == "PreToolUse" and agent_type == "dev" and (d.get("tool_name") or "") == "Bash":
    cmd = (d.get("tool_input") or {}).get("command") or ""
    import re as _re
    # Servidor de aplicação de longa duração — subir a app é do tester.
    # `run_in_background` por si NÃO entra aqui: medindo as 30 chamadas do `dev`, 21 eram
    # trabalho legítimo (uv run python -m ..., uv sync, scripts de análise, a suíte
    # typecheck+lint+test+build). Bloquear a flag quebraria o dev nos projetos Python/CLI.
    # Duas regras, validadas contra 46 comandos reais dos transcripts (20 que devem
    # bloquear, 26 que devem passar). Fronteiras importam: sem elas, `vite` casava dentro
    # de `vitest` e de `vite.config.ts`, e `dev` casava em `grep -rn dev src/`.
    SERV_BIN = _re.compile(r"(?:^|[\s;&|(])(?:vite(?![\w.\-/])|uvicorn|gunicorn"
                           r"|next\s+(?:dev|start)|flask\s+run|tsx\s+src/index"
                           r"|http\.server)", _re.I)
    SERV_PKG = _re.compile(r"(?:^|[\s;&|(])(?:pnpm|npm|yarn|bun|npx)\s+"
                           r"(?:run\s+|exec\s+)?(?:dev|start|preview|serve)(?=\s|$)", _re.I)
    BROWSER = _re.compile(r"\b(playwright|chromium|puppeteer|selenium)\b", _re.I)
    if (SERV_BIN.search(cmd) or SERV_PKG.search(cmd) or BROWSER.search(cmd)
            or _re.search(r"screenshot", cmd, _re.I)
            or _re.search(r"curl[^|;&]*\b(localhost|127\.0\.0\.1|0\.0\.0\.0|:\d{4})", cmd, _re.I)):
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "Subir servidor, rodar browser/E2E, tirar screenshot ou bater na app por HTTP "
                "é papel do `tester`, não seu. Entregue o que você implementou com "
                "`build_ok` (pode e deve rodar tsc/build/lint e teste unitário) e devolva "
                "`comandos_para_subir` — o Forge invoca o `tester`, que valida em contexto "
                "limpo e descartável. Validar aqui dobra o tamanho da sua invocação, e o "
                "contexto reenviado é o maior custo do loop."
            ),
        }}))
        sys.exit(10)

if event == "PostToolUse":
    n = read_count() + 1
    try: counter.write_text(str(n))
    except Exception: sys.exit(0)

    if n == warn:
        restante = cap - n
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"[orçamento de turnos] Você já fez {n} chamadas de ferramenta; o teto "
                f"desta invocação é {cap} (faltam {restante}). Contexto reenviado é o maior "
                "custo do Forge, e ele cresce a cada turno. Feche o que der para fechar agora. "
                "Se a tarefa não couber, devolva `status: \"PARCIAL\"` com `feito`, `falta` e "
                "`proximo_briefing` — o Forge re-loteia sem perder o seu trabalho. Insistir "
                "além do teto não é mais barato que devolver PARCIAL."
            ),
        }}))
    sys.exit(0)

if event == "PreToolUse":
    n = read_count()
    if n < cap:
        sys.exit(0)
    reason = (
        f"[orçamento de turnos esgotado] {n} chamadas de ferramenta nesta invocação "
        f"(teto {cap}). Pare de executar e RETORNE AGORA o JSON com "
        "`status: \"PARCIAL\"`, preenchendo `arquivos_alterados` com o que você já "
        "escreveu, `feito`, `falta` e `proximo_briefing` (o que o próximo dev precisa "
        "saber para continuar de onde você parou). O Forge vai re-lotear a tarefa. "
        "Não tente contornar o teto com outra ferramenta — todas estão negadas até o retorno."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(10)   # 10 = negado, veredito já impresso; o shell não delega ao rtk

sys.exit(0)
'
decision=$?

# Teto estourado: o deny já foi impresso. Nada mais a fazer.
[ "$decision" -eq 10 ] && exit 0

# Caminho liberado: se for um Bash no PreToolUse, deixa o rtk compactar a saída.
event=$(FORGE_HOOK_PAYLOAD="$payload" python3 -c '
import json, os
try: d = json.loads(os.environ["FORGE_HOOK_PAYLOAD"])
except Exception: raise SystemExit
print((d.get("hook_event_name") or "") + " " + (d.get("tool_name") or ""))
')

# Somente comandos de LEITURA com ganho medido e variante `rtk` liberada no settings.
# Nada que envolva push, deploy, escrita ou instalação de dependência entra aqui.
# Leitura/inspeção com ganho medido, e verificação (testes, tipos, lint) com ganho
# documentado de 83-99%. Testes entram porque o `dev` roda muito deles (234 chamadas de
# playwright, 229 de tsc, 85 de pytest nos transcripts) — hoje o output já é pequeno porque
# o Forge filtra na fonte, mas se o ciclo de teste crescer o filtro já está no lugar.
RTK_OK='^((uv[[:space:]]+run[[:space:]]+|pnpm[[:space:]]+exec[[:space:]]+|npx[[:space:]]+|python3?[[:space:]]+-m[[:space:]]+)?(jest|vitest|pytest|playwright|tsc|ruff|eslint)|git[[:space:]]+(status|diff|show|branch)|find|ls|tree)([[:space:]]|$)'

if [ "$event" = "PreToolUse Bash" ] && [ -x "$RTK_BIN" ]; then
    cmd=$(FORGE_HOOK_PAYLOAD="$payload" python3 -c '
import json, os
try: d = json.loads(os.environ["FORGE_HOOK_PAYLOAD"])
except Exception: raise SystemExit
print(((d.get("tool_input") or {}).get("command") or "").strip())
')
    if printf '%s' "$cmd" | grep -Eq "$RTK_OK"; then
        printf '%s' "$payload" | "$RTK_BIN" hook claude 2>/dev/null || true
    fi
fi

exit 0
