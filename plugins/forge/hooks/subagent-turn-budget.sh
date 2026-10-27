#!/usr/bin/env bash
# Teto de turnos por invocação de subagente — a maior alavanca de custo do Forge.
#
# POR QUE: o custo de uma invocação não cresce linear com os turnos, porque o contexto do
# subagente nunca é podado: o custo POR turno sobe conforme a invocação se alonga, então as
# invocações muito longas são desproporcionalmente caras.
#
# Sem teto, uma invocação pode rodar sem limite e ficar cada vez mais cara. Meça a
# distribuição no seu projeto com `bin/forge-tokens`.
#
# COMO: contamos chamadas de ferramenta (o payload não expõe turnos). Razão de calibração:
# 1,73 turno por chamada de ferramenta. Logo, nos tetos padrão do `dev`, 25 chamadas ≈ 43
# turnos (aviso) e 35 chamadas ≈ 60 turnos (teto).
#
# Trata dois eventos com o mesmo script:
#   PostToolUse → incrementa o contador e injeta o aviso (não pode bloquear)
#   PreToolUse  → nega a ferramenta acima do teto, forçando o retorno só em texto
#                (dev e genérico: PARCIAL; scout: PARCIAL; tester: FALHOU se achou defeito,
#                senão BLOQUEADO com "teto de turnos esgotado")
#
# E, quando LIBERA um Bash, delega ao `rtk hook claude` (Rust Token Killer), que reescreve
# o comando para a variante compacta. Por que encadeado aqui e não como hook separado: o
# hook do rtk devolve `permissionDecision: "allow"`, que competiria com o nosso `deny` no
# mesmo evento — dois vereditos, precedência indefinida. Encadeando, o veredito é um só e a
# ordem é garantida: o teto decide primeiro, o rtk só age no caminho liberado.
#
# O ganho do rtk varia conforme o perfil de comandos do projeto (compacta bem `git status`,
# `tree`, `find`; `cat`/`sed`/`grep` não têm o que comprimir); meça no seu projeto. As regras
# de briefing (usar Read/grep filtrado em vez de cat) atacam a mesma causa e valem sem o proxy.
#
# ⚠️ POR QUE A DELEGAÇÃO É RESTRITA A UMA LISTA (RTK_OK abaixo), e não "tudo que o rtk
# aceita": a reescrita acontece ANTES da checagem de permissão, então ela troca o comando
# que as regras de `permissions` vão avaliar. Deixar o rtk reescrever livremente traria
# dois problemas:
#   1. `git push` viraria `rtk git push` e deixava de casar com a regra `ask`
#      `Bash(git push:*)` — enfraquecendo a imposição do Invariante 2 (nunca push sozinho).
#   2. `cat`/`ls`/`find`/`pnpm install` saíam da allowlist (`Bash(cat:*)` não casa com
#      `rtk read ...`), o que geraria prompt de permissão em cada comando do loop.
# Então só delegamos comandos que (a) têm saída que o rtk sabe compactar, (b) são de leitura, e (c) têm a
# variante `rtk ...` explicitamente liberada em .claude/settings.json. Comando fora da lista
# segue nativo — o rtk nunca decide sozinho o que reescrever aqui.
#
# A sessão-raiz (orquestrador) não tem agent_id no payload e é ignorada aqui — seu
# limite é a compactação da própria sessão, não este contador.

payload=$(cat)
# rtk é opcional: usa $FORGE_RTK_BIN se definido, senão procura `rtk` no PATH, senão
# degrada em silêncio (RTK_BIN fica vazio e a delegação lá embaixo simplesmente não roda —
# nunca imprime erro nem bloqueia por falta do binário). Sem caminho absoluto de máquina:
# outra máquina pode não ter o rtk instalado.
RTK_BIN="${FORGE_RTK_BIN:-$(command -v rtk 2>/dev/null || true)}"

# Estado dos contadores de turno: fora do repo de quem instalou o plugin (senão sujaria o
# git de quem instalou). Preferência: $FORGE_STATE_DIR explícito > $XDG_RUNTIME_DIR >
# $TMPDIR > /tmp, sempre sob um subcaminho próprio (forge/turns) e separado por sessão
# quando o payload traz session_id — assim invocações concorrentes de sessões diferentes
# não disputam o mesmo diretório de contadores.
if [ -z "${FORGE_STATE_DIR:-}" ]; then
    _forge_runtime_base="${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}"
    _forge_session_id=$(FORGE_HOOK_PAYLOAD="$payload" python3 -c '
import json, os, re
try: d = json.loads(os.environ["FORGE_HOOK_PAYLOAD"])
except Exception: raise SystemExit
sid = d.get("session_id") or ""
print(re.sub(r"[^A-Za-z0-9_-]", "", sid)[:120])
' 2>/dev/null)
    if [ -n "$_forge_session_id" ]; then
        FORGE_STATE_DIR="${_forge_runtime_base}/forge/turns/${_forge_session_id}"
    else
        FORGE_STATE_DIR="${_forge_runtime_base}/forge/turns"
    fi
fi

FORGE_HOOK_PAYLOAD="$payload" \
FORGE_STATE_DIR="$FORGE_STATE_DIR" \
python3 -c '
import json, os, sys, time, pathlib

try:
    d = json.loads(os.environ.get("FORGE_HOOK_PAYLOAD", ""))
except Exception:
    sys.exit(0)  # payload ilegível: nunca atrapalha o trabalho

agent_id   = d.get("agent_id") or ""
agent_type = d.get("agent_type") or ""
# O runtime manda o tipo com o prefixo do plugin ("forge:dev", "forge:tester"). Só namespace
# vazio ou `forge` vale como papel dev/tester/scout; qualquer outro plugin (`outro:dev`) é
# genérico e recebe o teto genérico. `agent_full` guarda o nome completo para distinguir o
# plugin forge-visual, que tem tetos próprios e NÃO pode virar "dev"/"tester".
agent_full = agent_type
namespace, _, papel = agent_type.rpartition(":")
role       = papel if namespace in ("", "forge") else "outro"
is_visual  = agent_full.startswith("forge-visual:")
event      = d.get("hook_event_name") or ""

# Sem agent_id => sessão-raiz (o Forge). Não contamos o orquestrador.
if not agent_id:
    sys.exit(0)

# Tetos em CHAMADAS DE FERRAMENTA (~1,73 turno cada). Ajustáveis por env.
def env_int(name, default):
    try: return max(int(os.environ[name]), 1)
    except Exception: return default

# Teto por papel, pensado no trabalho típico de cada agente — um teto apertado demais
# estrangula o agente e gera retrabalho, que é o desperdício mais caro que existe. Papéis
# visuais e testers precisam de mais fôlego que scouts.
if is_visual:
    # Fluxo de construção visual: protótipos, iteração de shader, medição de FPS e contraste.
    # É longo por natureza (o fluxo visual itera sobre imagem e precisa de teto próprio). O teto aqui
    # existe só para pegar fuga de controle, não para apertar.
    if "tester" in papel:
        warn, cap = env_int("FORGE_VISUAL_TESTER_WARN", 50), env_int("FORGE_VISUAL_TESTER_CAP", 70)
    else:
        warn, cap = env_int("FORGE_VISUAL_WARN", 100), env_int("FORGE_VISUAL_CAP", 130)
elif role == "tester":
    # Sobe servidor, roda E2E e dirige o navegador: precisa de mais fôlego, por isso o
    # teto é folgado.
    warn, cap = env_int("FORGE_TESTER_WARN", 45), env_int("FORGE_TESTER_CAP", 65)
elif role == "scout":
    # Varredura tem muitas chamadas baratas (Glob/Grep/Read com limit) e roda em haiku, o
    # modelo mais barato do time. As chamadas são curtas — o teto sobra de propósito.
    warn, cap = env_int("FORGE_SCOUT_WARN", 28), env_int("FORGE_SCOUT_CAP", 40)
elif role == "dev":
    # A alavanca principal. O teto de 35 (≈60 turnos) pega as invocações longas e caras.
    # É um ponto intermediário de propósito: apertar mais economizaria mais, mas corta tarefas
    # no meio e o retrabalho de tarefa partida custa mais que a economia. Aperte com
    # FORGE_TURN_CAP depois de ver o efeito no `bin/forge-tokens`.
    warn, cap = env_int("FORGE_TURN_WARN", 25), env_int("FORGE_TURN_CAP", 35)
else:
    # Agentes genéricos (general-purpose, Explore, agentes de outros plugins): teto
    # moderado. Tratados como leitura/pesquisa.
    warn, cap = env_int("FORGE_OUTRO_WARN", 30), env_int("FORGE_OUTRO_CAP", 40)

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
# Sem esta regra, o `dev` pode validar a si mesmo e o `tester` ficar sem uso. Validar dentro
# da invocação do `dev` alonga a invocação, e as muito longas são as mais caras.
# Além do custo, é juiz em causa própria: o design diz que o `tester` é a palavra final.
#
# A linha de corte: o `dev` MANTÉM tsc/build/lint, teste unitário e qualquer script/processo
# próprio (inclusive em background) — é o `build_ok` que ele reporta. PERDE apenas subir a
# APLICAÇÃO, browser/E2E, screenshot e curl na app.
#
# Nem toda invocação de `dev` toca UI ou rota/API — nas outras (Python, script, config) o
# `tester` não se aplica, então a regra só pesa onde há superfície para validar.
if event == "PreToolUse" and role == "dev" and not is_visual and (d.get("tool_name") or "") == "Bash":
    cmd = (d.get("tool_input") or {}).get("command") or ""
    import re as _re
    # Servidor de aplicação de longa duração — subir a app é do tester.
    # `run_in_background` por si NÃO entra aqui: muitas dessas chamadas do `dev` são
    # trabalho legítimo (uv run python -m ..., uv sync, scripts de análise, a suíte
    # typecheck+lint+test+build). Bloquear a flag quebraria o dev nos projetos Python/CLI.
    # Duas regras, cobertas por testes com comandos que devem bloquear e comandos que devem
    # passar. Fronteiras importam: sem elas, `vite` casaria dentro
    # de `vitest` e de `vite.config.ts`, e `dev` casaria em `grep -rn dev src/`.
    SERV_BIN = _re.compile(r"(?:^|[\s;&|(])(?:vite(?![\w.\-/])(?!\s+build\b)|uvicorn|gunicorn"
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
        if role == "tester":
            saida = (
                "Se a validação não couber, pare: se já achou algum defeito do produto, "
                "devolva `FALHOU` com as `falhas` encontradas (um defeito achado já prova a "
                "falha); se não achou nenhum, devolva `BLOQUEADO` com "
                "`bloqueio.o_que_impediu: \"teto de turnos esgotado\"` e o que já validou "
                "em `evidencias`. O Forge te invoca de novo sem perder o que você apurou. "
                "Insistir além do teto não é mais barato que devolver o veredito."
            )
        elif role == "scout":
            saida = (
                "Se a varredura não couber, devolva `status: \"PARCIAL\"` com o que já "
                "apurou e o que ficou sem verificar — o Forge re-loteia sem perder o seu "
                "trabalho. Insistir além do teto não é mais barato que devolver PARCIAL."
            )
        else:
            saida = (
                "Se a tarefa não couber, devolva `status: \"PARCIAL\"` com `feito`, `falta` "
                "e `proximo_briefing` — o Forge re-loteia sem perder o seu trabalho. Insistir "
                "além do teto não é mais barato que devolver PARCIAL."
            )
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"[orçamento de turnos] Você já fez {n} chamadas de ferramenta; o teto "
                f"desta invocação é {cap} (faltam {restante}). Contexto reenviado é o maior "
                "custo do Forge, e ele cresce a cada turno. Feche o que der para fechar agora. "
                + saida
            ),
        }}))
    sys.exit(0)

if event == "PreToolUse":
    n = read_count()
    if n < cap:
        sys.exit(0)
    # Vale tanto para a primeira vez que o teto é atingido quanto para o agente retomado por
    # SendMessage que já estava no teto: a única saída é responder em texto, sem ferramenta.
    # A mensagem varia por papel: o `tester` não tem status PARCIAL (o veredito dele é
    # PASSOU/FALHOU/BLOQUEADO): defeito achado => FALHOU; nenhum => BLOQUEADO. O `scout`
    # devolve PARCIAL com o que apurou.
    cabeca = (
        f"[orçamento de turnos esgotado] {n} chamadas de ferramenta nesta invocação "
        f"(teto {cap}). NÃO tente outras ferramentas — todas estão negadas. Responda AGORA, "
        "só em texto, "
    )
    if role == "tester":
        corpo = (
            "com veredito: se já encontrou algum defeito do produto, `FALHOU` com as `falhas` "
            "encontradas (um defeito achado já prova a falha); se não encontrou nenhum, "
            "`BLOQUEADO` com `bloqueio.o_que_impediu: \"teto de turnos esgotado\"` e o que "
            "você já validou em `evidencias`. "
        )
        fim = "validar o restante"
    elif role == "scout":
        corpo = (
            "com `status: \"PARCIAL\"`: o que você já apurou e o que ficou sem verificar. "
        )
        fim = "completar a varredura"
    else:
        corpo = (
            "com `status: \"PARCIAL\"`: o que já foi feito, o que falta, os arquivos "
            "que você tocou (`arquivos_alterados`) e o estado de cada um (compila? completo? "
            "pela metade?), mais `proximo_briefing`. "
        )
        fim = "continuar"
    reason = (
        cabeca + corpo
        + f"Isso permite ao orquestrador despachar um agente NOVO, com contexto limpo, para {fim} "
        "a partir desse estado."
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

# Somente comandos de LEITURA cuja saída o rtk compacta e com variante `rtk` liberada no settings.
# Nada que envolva push, deploy, escrita ou instalação de dependência entra aqui.
# Leitura/inspeção, e verificação (testes, tipos, lint). Testes entram porque o `dev` roda
# muitos deles (playwright, tsc, pytest) e a saída deles costuma ser longa; filtrar na fonte
# continua valendo, e o rtk compacta o que sobrar.
# A allowlist (RTK_OK) vive em lib/rtk-bash-delegate.sh, compartilhada com o hook da
# sessão-raiz (rtk-root.sh) — não duplique a regex aqui.
if [ "$event" = "PreToolUse Bash" ]; then
    source "$(dirname "${BASH_SOURCE[0]}")/lib/rtk-bash-delegate.sh"
    rtk_delegate_if_allowed "$payload" "$RTK_BIN"
fi

exit 0
