#!/usr/bin/env python3
"""Testes do subagent-turn-budget.sh — teto de chamadas por papel de subagente.

    python3 plugins/forge/hooks/tests/test_subagent_turn_budget.py

O runtime manda `agent_type` com o prefixo do plugin (`forge:dev`); o hook normaliza para o
papel. Cada caso usa um FORGE_STATE_DIR temporário e semeia o contador do agente direto no
arquivo (nome = agent_id), em vez de disparar dezenas de chamadas.
"""
import json, os, shutil, subprocess, sys, tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "subagent-turn-budget.sh")
casos = []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn))
        return fn
    return deco


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _env(estado):
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("FORGE_"):
            del env[k]
    env["FORGE_STATE_DIR"] = estado
    env["FORGE_RTK_BIN"] = "/nonexistent/rtk"  # sem rtk: o hook nunca reescreve comando
    return env


def roda(estado, evento, agent_type, contador=None, agent_id="agente1", tool="Read",
         command=None):
    """Roda o hook; semeia o contador se pedido. Devolve (returncode, hookSpecificOutput|None)."""
    if contador is not None:
        with open(os.path.join(estado, agent_id), "w") as f:
            f.write(str(contador))
    entrada = {"hook_event_name": evento, "tool_name": tool, "agent_id": agent_id,
               "agent_type": agent_type, "session_id": "s"}
    if command is not None:
        entrada["tool_input"] = {"command": command}
    r = subprocess.run(["bash", HOOK], input=json.dumps(entrada), capture_output=True,
                       text=True, env=_env(estado))
    saida = json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None
    return r.returncode, saida


class Estado:
    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix="forge-turns-test-")
        return self.dir

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)


def aviso(estado, agent_type, warn):
    """Aviso do teto: contador em warn-1, uma PostToolUse leva a warn."""
    _, out = roda(estado, "PostToolUse", agent_type, contador=warn - 1)
    return out["additionalContext"] if out else None


def ctx_cita(ctx, warn, cap):
    return ctx is not None and f"{warn} chamadas" in ctx and f"é {cap} " in ctx


@caso("forge:dev recebe o teto do dev (aviso 25, teto 35)")
def _():
    with Estado() as e:
        ctx = aviso(e, "forge:dev", 25)
        ok(ctx_cita(ctx, 25, 35), f"aviso inesperado: {ctx!r}")
        ok(aviso(e, "dev", 25) == ctx, "`dev` e `forge:dev` deveriam ser equivalentes")


@caso("forge:dev é barrado ao subir servidor, browser, screenshot ou curl na app")
def _():
    with Estado() as e:
        for cmd in ("pnpm dev", "cd frontend && pnpm vite", "npx playwright test",
                    "uvicorn app:app", "curl http://localhost:3000/api",
                    "vite", "vite dev", "vite preview", "vite --port 5173", "npx vite"):
            rc, out = roda(e, "PreToolUse", "forge:dev", contador=1, tool="Bash", command=cmd)
            ok(out and out["permissionDecision"] == "deny", f"deveria barrar {cmd!r}")
            ok("tester" in out["permissionDecisionReason"], "razão deveria citar o tester")
        for cmd in ("pnpm build 2>&1 | tail -30", "pnpm vitest run", "vite build",
                    "npx vite build", "pnpm vite build"):
            rc, out = roda(e, "PreToolUse", "forge:dev", contador=1, tool="Bash", command=cmd)
            ok(out is None, f"{cmd!r} é do dev, não deveria barrar: {out!r}")


@caso("forge:tester NÃO é barrado ao subir servidor")
def _():
    with Estado() as e:
        rc, out = roda(e, "PreToolUse", "forge:tester", contador=1, tool="Bash",
                       command="pnpm dev")
        ok(out is None, f"tester pode subir servidor: {out!r}")


@caso("forge:tester recebe o teto do tester (aviso 45, teto 65)")
def _():
    with Estado() as e:
        ctx = aviso(e, "forge:tester", 45)
        ok(ctx_cita(ctx, 45, 65), f"aviso inesperado: {ctx!r}")


@caso("aviso do tester: FALHOU se achou defeito, BLOQUEADO se não, sem PARCIAL")
def _():
    with Estado() as e:
        ctx = aviso(e, "forge:tester", 45)
        for trecho in ("FALHOU", "BLOQUEADO", "teto de turnos esgotado", "`falhas`",
                       "`evidencias`"):
            ok(trecho in ctx, f"aviso do tester sem {trecho!r}: {ctx!r}")
        ok("PARCIAL" not in ctx, f"tester não tem status PARCIAL: {ctx!r}")


@caso("aviso de dev, scout e genérico: PARCIAL; sem veredito do tester")
def _():
    with Estado() as e:
        for tipo, warn in (("forge:dev", 25), ("forge:scout", 28), ("general-purpose", 30)):
            ctx = aviso(e, tipo, warn)
            ok("PARCIAL" in ctx, f"{tipo}: aviso sem PARCIAL: {ctx!r}")
            ok("FALHOU" not in ctx and "BLOQUEADO" not in ctx,
               f"{tipo}: aviso não deveria falar de veredito: {ctx!r}")
        ok("apurou" in aviso(e, "forge:scout", 28), "scout deveria citar o que apurou")
        ok("proximo_briefing" in aviso(e, "forge:dev", 25), "dev deveria citar proximo_briefing")


@caso("forge:scout recebe o teto do scout (aviso 28, teto 40)")
def _():
    with Estado() as e:
        ctx = aviso(e, "forge:scout", 28)
        ok(ctx_cita(ctx, 28, 40), f"aviso inesperado: {ctx!r}")
        ok(aviso(e, "forge:scout", 25) is None, "scout não deveria avisar com 25")


@caso("general-purpose recebe o teto genérico (aviso 30, teto 40)")
def _():
    with Estado() as e:
        ctx = aviso(e, "general-purpose", 30)
        ok(ctx_cita(ctx, 30, 40), f"aviso inesperado: {ctx!r}")
        ok(aviso(e, "general-purpose", 25) is None, "genérico não deveria avisar com 25")


@caso("outro:dev (outro plugin) é genérico: sem aviso do dev com 25 chamadas, aviso em 30")
def _():
    with Estado() as e:
        ok(aviso(e, "outro:dev", 25) is None, "outro:dev não deveria receber o aviso do dev")
        ctx = aviso(e, "outro:dev", 30)
        ok(ctx_cita(ctx, 30, 40), f"aviso inesperado: {ctx!r}")


@caso("outro:dev NÃO é barrado ao subir servidor (a regra do dev é só do forge)")
def _():
    with Estado() as e:
        rc, out = roda(e, "PreToolUse", "outro:dev", contador=1, tool="Bash", command="pnpm dev")
        ok(out is None, f"outro:dev não deveria ser barrado: {out!r}")


@caso("forge-visual:visual-dev mantém o teto visual e não vira `dev`")
def _():
    with Estado() as e:
        ctx = aviso(e, "forge-visual:visual-dev", 100)
        ok(ctx_cita(ctx, 100, 130), f"aviso inesperado: {ctx!r}")
        rc, out = roda(e, "PreToolUse", "forge-visual:dev", contador=1, tool="Bash",
                       command="pnpm dev")
        ok(out is None, "plugin visual não herda a regra do dev")


def _nega_no_teto(e, tipo, cap):
    rc, out = roda(e, "PreToolUse", tipo, contador=cap - 1)
    ok(out is None, f"{tipo}: abaixo do teto não deveria negar")
    rc, out = roda(e, "PreToolUse", tipo, contador=cap)
    ok(out and out["permissionDecision"] == "deny", f"{tipo}: deveria negar no teto")
    razao = out["permissionDecisionReason"]
    for trecho in ("NÃO tente outras ferramentas", "só em texto", "agente NOVO"):
        ok(trecho in razao, f"{tipo}: mensagem sem {trecho!r}: {razao!r}")
    # retomada por SendMessage: contador continua no teto, mesma negação
    rc, out2 = roda(e, "PreToolUse", tipo)
    ok(out2 and out2["permissionDecisionReason"] == razao,
       f"{tipo}: retomada deveria repetir a mensagem")
    return razao


@caso("teto esgotado do dev: mensagem PARCIAL com feito, falta, arquivos e estado")
def _():
    with Estado() as e:
        razao = _nega_no_teto(e, "forge:dev", 35)
        for trecho in ("PARCIAL", "o que já foi feito", "o que falta", "arquivos", "estado"):
            ok(trecho in razao, f"dev: mensagem sem {trecho!r}: {razao!r}")


@caso("teto esgotado do tester: FALHOU se achou defeito, BLOQUEADO se não, sem PARCIAL")
def _():
    with Estado() as e:
        razao = _nega_no_teto(e, "forge:tester", 65)
        for trecho in ("FALHOU", "BLOQUEADO", "bloqueio.o_que_impediu", "teto de turnos esgotado",
                       "`evidencias`", "`falhas`", "defeito"):
            ok(trecho in razao, f"tester: mensagem sem {trecho!r}: {razao!r}")
        ok("PARCIAL" not in razao, f"tester não tem status PARCIAL: {razao!r}")


@caso("teto esgotado do scout: PARCIAL com o que apurou e o que ficou sem verificar")
def _():
    with Estado() as e:
        razao = _nega_no_teto(e, "forge:scout", 40)
        for trecho in ("o que você já apurou", "sem verificar"):
            ok(trecho in razao, f"scout: mensagem sem {trecho!r}: {razao!r}")
        ok("PARCIAL" in razao, f"scout deveria usar PARCIAL: {razao!r}")


@caso("teto esgotado de outros papéis: texto genérico PARCIAL")
def _():
    with Estado() as e:
        razao = _nega_no_teto(e, "general-purpose", 40)
        ok("PARCIAL" in razao, f"genérico deveria usar PARCIAL: {razao!r}")


@caso("sessão-raiz (sem agent_id) é ignorada")
def _():
    with Estado() as e:
        entrada = {"hook_event_name": "PreToolUse", "tool_name": "Read",
                   "agent_type": "forge:dev"}
        r = subprocess.run(["bash", HOOK], input=json.dumps(entrada), capture_output=True,
                           text=True, env=_env(e))
        ok(r.returncode == 0 and not r.stdout.strip(), f"deveria ficar calado: {r.stdout!r}")


def main():
    falhas = 0
    for nome, fn in casos:
        try:
            fn()
        except Exception as ex:
            falhas += 1
            print(f"FALHOU  {nome}\n        {type(ex).__name__}: {ex}")
        else:
            print(f"ok      {nome}")
    print(f"\n{len(casos) - falhas}/{len(casos)} casos passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
