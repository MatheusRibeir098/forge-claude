#!/usr/bin/env python3
"""Testes do hook `require-tester.py` — só stdlib, sem dependência externa.

    python3 .claude/hooks/tests/test_require_tester.py

Todo payload é montado a partir de um PostToolUse REAL capturado na CLI 2.1.272
(`fixtures/posttooluse-agent-completed.json`): copiamos o envelope de verdade e trocamos
apenas `tool_input.subagent_type` e o texto do retorno. Assim o teste não valida um formato
inventado — se a CLI mudar o envelope de novo, basta recapturar a fixture.
"""
import copy
import json
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(os.path.dirname(AQUI), "require-tester.py")
FIXTURE = os.path.join(AQUI, "fixtures", "posttooluse-agent-completed.json")

with open(FIXTURE, encoding="utf-8") as fh:
    ENVELOPE_REAL = json.load(fh)


def payload(texto_retorno, *, subagent_type="dev", prompt="implementar a tarefa",
            description="tarefa", status="completed", agent_id=None, tool_response=True):
    """Envelope real com o miolo trocado."""
    d = copy.deepcopy(ENVELOPE_REAL)
    d["tool_input"] = {"description": description, "prompt": prompt,
                       "subagent_type": subagent_type, "run_in_background": False}
    if not tool_response:
        d.pop("tool_response", None)
        return d
    d["tool_response"]["status"] = status
    d["tool_response"]["agentType"] = subagent_type
    d["tool_response"]["content"] = [{"type": "text", "text": texto_retorno}]
    if agent_id:
        d["agent_id"] = agent_id
    return d


def cerca(obj):
    """Como o `dev` devolve de verdade: JSON dentro de cerca ```json."""
    return "```json\n" + json.dumps(obj, ensure_ascii=False) + "\n```"


def roda(entrada):
    """Executa o hook. Devolve (returncode, stdout, additionalContext ou None)."""
    bruto = entrada if isinstance(entrada, str) else json.dumps(entrada, ensure_ascii=False)
    p = subprocess.run([sys.executable, HOOK], input=bruto, capture_output=True, text=True)
    ctx = None
    if p.stdout.strip():
        ctx = json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"]
    return p.returncode, p.stdout, ctx


# --------------------------------------------------------------------------- casos

CASOS = []


def caso(nome):
    def deco(fn):
        CASOS.append((nome, fn))
        return fn
    return deco


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


@caso("(a) retorno com .tsx + comandos_para_subir -> modo browser")
def _a():
    rc, _, ctx = roda(payload(cerca({
        "status": "OK",
        "arquivos_alterados": ["src/components/Dashboard.tsx", "src/styles/app.css"],
        "build_ok": True,
        "comandos_para_subir": ["npm install", "npm run dev -- --port 5173"],
        "resumo": "dashboard novo",
        "pendencias": [],
    })))
    ok(rc == 0, f"exit {rc}")
    ok(ctx is not None, "não injetou nada")
    ok("modo browser" in ctx, f"não recomendou browser: {ctx!r}")
    ok("modo contrato" not in ctx, "recomendou dois modos")
    ok("Dashboard.tsx" in ctx and "app.css" in ctx, "não listou arquivos_alterados reais")
    ok("npm run dev -- --port 5173" in ctx, "não trouxe comandos_para_subir literais")
    ok("print" in ctx, "modo browser deveria falar em print")


@caso("(b) retorno só com .ts de mcp-server -> modo contrato, nunca browser")
def _b():
    rc, _, ctx = roda(payload(cerca({
        "status": "OK",
        "arquivos_alterados": ["packages/mcp-server/src/adapters/quicksight.ts"],
        "build_ok": True,
        "comandos_para_subir": [],
        "resumo": "adapter novo",
    })))
    ok(rc == 0, f"exit {rc}")
    ok(ctx is not None, "não injetou nada")
    ok("modo contrato" in ctx, f"não recomendou contrato: {ctx!r}")
    ok("modo browser" not in ctx, "FALSO POSITIVO: mcp-server virou browser")
    ok("quicksight.ts" in ctx, "não listou o arquivo")


@caso("(b2) mcp_server, server.test.ts e vite.config.ts nunca disparam browser")
def _b2():
    for arquivos, comandos in (
        (["src/mcp_server/handlers/tools.py"], ["python -m src.mcp_server"]),
        (["packages/api/src/server.test.ts"], []),
        (["vite.config.ts"], ["npm run dev"]),
        (["config/webpack.config.js", "tsconfig.json"], ["npm run build"]),
    ):
        _, _, ctx = roda(payload(cerca({
            "status": "OK", "arquivos_alterados": arquivos, "build_ok": True,
            "comandos_para_subir": comandos, "resumo": "x"})))
        ok(ctx is None or "modo browser" not in ctx,
           f"FALSO POSITIVO browser em {arquivos}: {ctx!r}")
    # teste e config de build sozinhos não podem gerar lembrete nenhum
    _, _, ctx = roda(payload(cerca({
        "status": "OK", "arquivos_alterados": ["packages/api/src/server.test.ts"],
        "build_ok": True, "comandos_para_subir": [], "resumo": "x"})))
    ok(ctx is None, f"teste puro deveria ser silêncio: {ctx!r}")


@caso("(c) retorno só com .md / teste -> silêncio")
def _c():
    rc, out, ctx = roda(payload(cerca({
        "status": "OK",
        "arquivos_alterados": ["README.md", "docs/arquitetura.md",
                               "src/lib/parser.test.ts", "src/types/domain.d.ts"],
        "build_ok": True,
        "comandos_para_subir": [],
        "resumo": "doc e teste",
    })))
    ok(rc == 0, f"exit {rc}")
    ok(out.strip() == "", f"deveria ficar calado, injetou: {ctx!r}")


@caso("(d) status BLOQUEADO -> silêncio")
def _d():
    rc, out, _ = roda(payload(cerca({
        "status": "BLOQUEADO",
        "arquivos_alterados": ["src/pages/Home.tsx"],
        "build_ok": False,
        "comandos_para_subir": ["npm run dev"],
        "resumo": "faltou credencial",
        "pendencias": ["sem token"],
    })))
    ok(rc == 0, f"exit {rc}")
    ok(out.strip() == "", "BLOQUEADO não tem o que validar, deveria ficar calado")


@caso("(e) JSON do dev não parseável -> fallback pelo briefing")
def _e():
    rc, _, ctx = roda(payload(
        "Fiz a tela de login e o roteamento. Não vou devolver JSON desta vez.",
        prompt="ajuste o src/pages/Login.tsx e o tema em src/styles/theme.scss"))
    ok(rc == 0, f"exit {rc}")
    ok(ctx is not None, "fallback não injetou nada")
    ok("FALLBACK" in ctx.upper(), f"não marcou que foi fallback: {ctx!r}")
    ok("Login.tsx" in ctx, "fallback não citou o arquivo do briefing")


@caso("(e2) fallback ignora palavra genérica sem arquivo renderizável")
def _e2():
    rc, out, _ = roda(payload(
        "Pronto, terminei.",
        prompt="ajuste o layout do dashboard e a rota do endpoint no servidor"))
    ok(rc == 0, f"exit {rc}")
    ok(out.strip() == "", "palavra genérica voltou a disparar lembrete (era o ruído antigo)")


@caso("(f) payload ilegível -> exit 0 silencioso")
def _f():
    for bruto in ("", "isto não é json", "[1,2,3]", "null", '{"tool_input": 42}'):
        rc, out, _ = roda(bruto)
        ok(rc == 0, f"exit {rc} para {bruto!r}")
        ok(out.strip() == "", f"falou em payload ilegível {bruto!r}: {out!r}")


@caso("(g) agent_id presente -> silêncio (só a sessão-raiz orquestra)")
def _g():
    rc, out, _ = roda(payload(cerca({
        "status": "OK", "arquivos_alterados": ["src/App.tsx"], "build_ok": True,
        "comandos_para_subir": ["npm run dev"], "resumo": "x"}), agent_id="a93b7aa2fcdf0fbba"))
    ok(rc == 0, f"exit {rc}")
    ok(out.strip() == "", "subagente despachando subagente não deveria gerar lembrete")


@caso("(h) subagent_type scout -> silêncio")
def _h():
    for tipo in ("scout", "tester", "spike-dev", ""):
        rc, out, _ = roda(payload(cerca({
            "status": "OK", "arquivos_alterados": ["src/App.tsx"], "build_ok": True,
            "comandos_para_subir": ["npm run dev"], "resumo": "x"}), subagent_type=tipo))
        ok(rc == 0, f"exit {rc}")
        ok(out.strip() == "", f"subagent_type {tipo!r} não deveria gerar lembrete")


@caso("(i) status != completed (async/erro) -> silêncio")
def _i():
    for st in ("async_launched", "error", "cancelled"):
        rc, out, _ = roda(payload(cerca({
            "status": "OK", "arquivos_alterados": ["src/App.tsx"], "build_ok": True,
            "comandos_para_subir": ["npm run dev"], "resumo": "x"}), status=st))
        ok(rc == 0, f"exit {rc}")
        ok(out.strip() == "", f"status {st!r} não deveria gerar lembrete")
    rc, out, _ = roda(payload("", tool_response=False))
    ok(rc == 0 and out.strip() == "", "sem tool_response deveria ficar calado")


@caso("(j) .yaml aplicado e comandos sem renderizável -> modo contrato")
def _j():
    _, _, ctx = roda(payload(cerca({
        "status": "OK", "arquivos_alterados": ["dashboards/vendas.dsl.yaml"],
        "build_ok": True, "comandos_para_subir": [], "resumo": "yaml"})))
    ok(ctx and "modo contrato" in ctx, f"yaml deveria ser contrato: {ctx!r}")
    _, _, ctx = roda(payload(cerca({
        "status": "OK", "arquivos_alterados": ["src/core/compiler.py"],
        "build_ok": True, "comandos_para_subir": ["python -m compiler build"],
        "resumo": "compilador"})))
    ok(ctx and "modo contrato" in ctx, f"comandos sem renderizável = contrato: {ctx!r}")
    ok("python -m compiler build" in ctx, "não trouxe o comando literal")
    ok("print" not in ctx, "modo contrato não deve pedir print")


@caso("(k) .tsx sem comandos_para_subir -> contrato, nunca browser")
def _k():
    _, _, ctx = roda(payload(cerca({
        "status": "OK", "arquivos_alterados": ["src/components/Card.tsx"],
        "build_ok": True, "comandos_para_subir": [], "resumo": "card"})))
    ok(ctx is not None, "não injetou nada")
    ok("modo browser" not in ctx, "browser exige comandos_para_subir")
    ok("modo contrato" in ctx, f"esperava contrato: {ctx!r}")


@caso("(l) texto solto em volta da cerca e lista longa truncada em 5")
def _l():
    arquivos = [f"src/views/Tela{i}.tsx" for i in range(1, 9)]
    corpo = ("Terminei a tarefa. Segue o retorno:\n\n"
             + cerca({"status": "OK", "arquivos_alterados": arquivos, "build_ok": True,
                      "comandos_para_subir": ["pnpm dev"], "resumo": "8 telas"})
             + "\n\nQualquer coisa me chame.")
    _, _, ctx = roda(payload(corpo))
    ok(ctx and "modo browser" in ctx, f"não achou o JSON no texto solto: {ctx!r}")
    ok("Tela5.tsx" in ctx and "Tela6.tsx" not in ctx, "não truncou em 5")
    ok("…" in ctx, "não marcou o truncamento")
    ok("pnpm dev" in ctx, "perdeu o comando literal")


@caso("(m) fixtures reais capturadas na CLI 2.1.272 não quebram o hook")
def _m():
    base = os.path.join(AQUI, "fixtures")
    for nome in sorted(os.listdir(base)):
        with open(os.path.join(base, nome), encoding="utf-8") as fh:
            d = json.load(fh)
        rc, _, _ = roda(d)
        ok(rc == 0, f"exit {rc} na fixture {nome}")
        ok(d["tool_response"]["status"] == "completed",
           f"fixture {nome} deveria ter status completed")
        ok(isinstance(d["tool_response"]["content"][0]["text"], str),
           f"fixture {nome} sem content[0].text")


def main():
    falhas = 0
    for nome, fn in CASOS:
        try:
            fn()
        except Exception as e:
            falhas += 1
            print(f"FALHOU  {nome}\n        {type(e).__name__}: {e}")
        else:
            print(f"ok      {nome}")
    total = len(CASOS)
    print(f"\n{total - falhas}/{total} casos passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
