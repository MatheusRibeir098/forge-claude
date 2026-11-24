#!/usr/bin/env python3
"""Testes do hook `require-tester.py` — só stdlib, sem dependência externa.

    python3 plugins/forge/hooks/tests/test_require_tester.py

Todo payload é montado a partir de um PostToolUse REAL capturado na CLI 2.1.272
(`fixtures/posttooluse-agent-completed.json`): copiamos o envelope de verdade e trocamos
apenas `tool_input.subagent_type` e o texto do retorno. Assim o teste não valida um formato
inventado — se a CLI mudar o envelope, basta recapturar a fixture.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(os.path.dirname(AQUI), "require-tester.py")
FIXTURE = os.path.join(AQUI, "fixtures", "posttooluse-agent-completed.json")

with open(FIXTURE, encoding="utf-8") as fh:
    ENVELOPE_REAL = json.load(fh)


# Pasta de estado do caso em curso (cada caso é uma sessão nova); trocada pelo main().
ESTADO = [""]


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
    # cada invocação real tem `agentId` próprio; o hook deduplica por ele
    CONTADOR[0] += 1
    d["tool_response"]["agentId"] = f"a{CONTADOR[0]:016x}"
    d["tool_response"]["content"] = [{"type": "text", "text": texto_retorno}]
    if agent_id:
        d["agent_id"] = agent_id
    return d


CONTADOR = [0]


def cerca(obj):
    """Como o `dev` devolve de verdade: JSON dentro de cerca ```json."""
    return "```json\n" + json.dumps(obj, ensure_ascii=False) + "\n```"


def roda(entrada):
    """Executa o hook. Devolve (returncode, stdout, additionalContext ou None)."""
    bruto = entrada if isinstance(entrada, str) else json.dumps(entrada, ensure_ascii=False)
    env = dict(os.environ, FORGE_STATE_DIR=ESTADO[0])
    p = subprocess.run([sys.executable, HOOK], input=bruto, capture_output=True, text=True,
                       env=env)
    ctx = None
    if p.stdout.strip():
        ctx = json.loads(p.stdout).get("hookSpecificOutput", {}).get("additionalContext")
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
        if not nome.startswith("posttooluse-agent-completed"):
            continue  # as demais são de SubagentStop/Stop/async, cobertas abaixo
        with open(os.path.join(base, nome), encoding="utf-8") as fh:
            d = json.load(fh)
        rc, _, _ = roda(d)
        ok(rc == 0, f"exit {rc} na fixture {nome}")
        ok(d["tool_response"]["status"] == "completed",
           f"fixture {nome} deveria ter status completed")
        ok(isinstance(d["tool_response"]["content"][0]["text"], str),
           f"fixture {nome} sem content[0].text")

# ----------------------------------------------------- ordem dos eventos e vereditos

ENTREGA_UI = {"status": "OK", "arquivos_alterados": ["src/components/Card.tsx"],
              "build_ok": True, "comandos_para_subir": ["pnpm dev"], "resumo": "card"}


def dev_entrega():
    return payload(cerca(ENTREGA_UI))


def tester_diz(veredito, tipo="tester", **extra):
    corpo = {"modo": "browser", "veredito": veredito, "falhas": [], "evidencias": [],
             "logs_relevantes": [], "recomendacao_para_dev": ""}
    corpo.update(extra)
    return payload(cerca(corpo), subagent_type=tipo)


def pendente():
    return os.path.isfile(os.path.join(ESTADO[0], "pendente"))


@caso("(n) dev marca a pendência e PASSOU a limpa, em silêncio")
def _n():
    _, _, ctx = roda(dev_entrega())
    ok(ctx and "validação pendente" in ctx, "dev não pediu validação")
    ok(pendente(), "dev não deixou pendência")
    rc, out, _ = roda(tester_diz("PASSOU"))
    ok(rc == 0 and out.strip() == "", f"PASSOU deveria ser silencioso: {out!r}")
    ok(not pendente(), "PASSOU não limpou a pendência")


@caso("(o) dev depois de PASSOU reabre a pendência")
def _o():
    roda(dev_entrega())
    roda(tester_diz("PASSOU"))
    ok(not pendente(), "PASSOU não limpou a pendência")
    _, _, ctx = roda(dev_entrega())
    ok(ctx and "validação pendente" in ctx, "segundo dev não voltou a pedir validação")
    ok(pendente(), "dev depois do PASSOU não reabriu a pendência")
    roda(tester_diz("PASSOU"))
    ok(not pendente(), "novo PASSOU não limpou a pendência")


@caso("(p) BLOQUEADO não aprova: mantém a pendência e manda resolver o ambiente")
def _p():
    roda(dev_entrega())
    rc, _, ctx = roda(tester_diz(
        "BLOQUEADO", bloqueio={"o_que_impediu": "extensão do Chrome indisponível",
                               "o_que_destravaria": "abrir o Chrome com a extensão"}))
    ok(rc == 0, f"exit {rc}")
    ok(ctx and "BLOQUEADA" in ctx, f"não sinalizou BLOQUEADO: {ctx!r}")
    ok("NÃO aprovada" in ctx and "não é aprovação" in ctx, "não negou a aprovação")
    ok("ambiente" in ctx and "usuário" in ctx, "não mandou resolver o ambiente/perguntar")
    ok("extensão do Chrome indisponível" in ctx, "não repetiu o que impediu")
    ok(pendente(), "BLOQUEADO limpou a pendência (aprovou por engano)")


@caso("(q) FALHOU mantém a pendência e manda devolver ao dev")
def _q():
    roda(dev_entrega())
    _, _, ctx = roda(tester_diz(
        "FALHOU", falhas=[{"tipo": "visual", "onde": "Card", "viewport": "mobile",
                           "descricao": "botão sai 40px do container"}],
        recomendacao_para_dev="conter o botão"))
    ok(ctx and "FALHOU" in ctx, f"não sinalizou FALHOU: {ctx!r}")
    ok("botão sai 40px do container" in ctx and "conter o botão" in ctx, "perdeu a descrição")
    ok("NÃO está aprovada" in ctx, "não negou a aprovação")
    ok(pendente(), "FALHOU limpou a pendência")


@caso("(r) veredito ilegível com pendência -> lembra; sem pendência -> silêncio")
def _r():
    sem = payload("terminei, tudo certo", subagent_type="tester")
    rc, out, _ = roda(sem)
    ok(rc == 0 and out.strip() == "", "sem pendência deveria ficar calado")
    roda(dev_entrega())
    _, _, ctx = roda(sem)
    ok(ctx and "veredito" in ctx, f"não avisou que não há veredito: {ctx!r}")
    ok(pendente(), "retorno sem veredito limpou a pendência")


@caso("(s) dev BLOQUEADO ou só doc não reabre nem cria pendência")
def _s():
    roda(payload(cerca({"status": "BLOQUEADO", "arquivos_alterados": ["src/A.tsx"],
                        "comandos_para_subir": ["pnpm dev"], "pendencias": ["x"]})))
    roda(payload(cerca({"status": "OK", "arquivos_alterados": ["README.md"],
                        "comandos_para_subir": []})))
    ok(not pendente(), "retorno sem entrega validável criou pendência")
    roda(dev_entrega())
    roda(tester_diz("PASSOU"))
    roda(payload(cerca({"status": "OK", "arquivos_alterados": ["README.md"],
                        "comandos_para_subir": []})))
    ok(not pendente(), "doc depois de PASSOU não deveria reabrir")


@caso("(t) tester ilegível ou agent_id -> exit 0 silencioso e sem tocar o estado")
def _t():
    roda(dev_entrega())
    for entrada in (payload("x", subagent_type="tester", status="error"),
                    tester_diz("PASSOU") | {"agent_id": "sub1"}):
        rc, out, _ = roda(entrada)
        ok(rc == 0 and out.strip() == "", f"deveria ficar calado: {out!r}")
    ok(pendente(), "evento ignorado alterou a pendência")


FORGE_DEV = "forge:dev"
FORGE_TESTER = "forge:tester"


def dev_forge():
    return payload(cerca(ENTREGA_UI), subagent_type=FORGE_DEV)


@caso("(u) forge:dev e forge:tester (plugin instalado): browser, FALHOU e PASSOU")
def _u():
    _, _, ctx = roda(dev_forge())
    ok(ctx and "modo browser" in ctx, f"forge:dev não pediu browser: {ctx!r}")
    ok(pendente(), "forge:dev não deixou pendência")
    _, _, ctx = roda(tester_diz("FALHOU", tipo=FORGE_TESTER, recomendacao_para_dev="conter"))
    ok(ctx and "FALHOU" in ctx, f"forge:tester FALHOU não foi tratado: {ctx!r}")
    ok(pendente(), "FALHOU de forge:tester limpou a pendência")
    rc, out, _ = roda(tester_diz("PASSOU", tipo=FORGE_TESTER))
    ok(rc == 0 and out.strip() == "", f"PASSOU deveria ser silencioso: {out!r}")
    ok(not pendente(), "PASSOU de forge:tester não limpou a pendência")


@caso("(v) com forge:*, só PASSOU posterior ao último dev aprova")
def _v():
    roda(dev_forge())
    roda(tester_diz("PASSOU", tipo=FORGE_TESTER))
    ok(not pendente(), "PASSOU não limpou a pendência")
    _, _, ctx = roda(dev_forge())
    ok(ctx and "validação pendente" in ctx, "forge:dev após PASSOU não reabriu o pedido")
    ok(pendente(), "forge:dev após PASSOU não reabriu a pendência")
    roda(tester_diz("BLOQUEADO", tipo=FORGE_TESTER))
    ok(pendente(), "BLOQUEADO aprovou por engano")
    roda(tester_diz("PASSOU", tipo=FORGE_TESTER))
    ok(not pendente(), "PASSOU posterior ao último dev não aprovou")


@caso("(w) namespace de outro plugin (outro:dev, outro:tester) fica em silêncio")
def _w():
    rc, out, _ = roda(payload(cerca(ENTREGA_UI), subagent_type="outro:dev"))
    ok(rc == 0 and out.strip() == "", f"outro:dev deveria ficar calado: {out!r}")
    ok(not pendente(), "outro:dev criou pendência")
    roda(dev_forge())
    rc, out, _ = roda(tester_diz("PASSOU", tipo="outro:tester"))
    ok(rc == 0 and out.strip() == "", f"outro:tester deveria ficar calado: {out!r}")
    ok(pendente(), "outro:tester limpou a pendência")


# ------------------------------------- CLI 2.1.331: lançamento assíncrono + SubagentStop/Stop
# Envelopes em fixtures/ montados com as chaves medidas por hook de log na 2.1.331.

def _fixture(nome):
    with open(os.path.join(AQUI, "fixtures", nome), encoding="utf-8") as fh:
        return json.load(fh)


def transcript(briefing):
    """Transcript do subagente (fixture real) com o briefing trocado, na pasta do caso."""
    caminho = os.path.join(ESTADO[0], f"transcript-{CONTADOR[0]}.jsonl")
    CONTADOR[0] += 1
    with open(os.path.join(AQUI, "fixtures", "subagent-transcript.jsonl"), encoding="utf-8") as fh:
        linhas = [json.loads(linha) for linha in fh if linha.strip()]
    linhas[0]["message"]["content"] = briefing
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(linha, ensure_ascii=False) for linha in linhas))
    return caminho


def sub_stop(mensagem, *, tipo="forge:dev", agent_id="ab38432b42d35d52a",
             briefing="implementar a tarefa"):
    d = _fixture("subagentstop-dev.json")
    d.update(agent_type=tipo, agent_id=agent_id, last_assistant_message=mensagem,
             agent_transcript_path=transcript(briefing))
    return d


def stop(**extra):
    return _fixture("stop.json") | extra


def tester_lancado(agent_id=None):
    d = _fixture("posttooluse-agent-async-launched.json")
    if agent_id:
        d["agent_id"] = agent_id
    return d


def entregas():
    caminho = os.path.join(ESTADO[0], "pendente")
    if not os.path.isfile(caminho):
        return []
    with open(caminho, encoding="utf-8") as fh:
        return json.load(fh)["entregas"]


def bloqueio(out):
    d = json.loads(out) if out.strip() else {}
    return d.get("reason") if d.get("decision") == "block" else None


VEREDITO = {"modo": "browser", "falhas": [], "evidencias": [], "recomendacao_para_dev": ""}


@caso("(x) SubagentStop dev OK com .tsx + comandos -> pendência browser, sem imprimir")
def _x():
    rc, out, _ = roda(sub_stop(cerca(ENTREGA_UI)))
    ok(rc == 0 and out.strip() == "", f"SubagentStop não pode imprimir: {out!r}")
    e = entregas()
    ok(len(e) == 1 and e[0]["modo"] == "browser", f"esperava 1 entrega browser: {e!r}")
    ok(e[0]["arquivos"] == ["src/components/Card.tsx"] and e[0]["agent_id"], f"{e!r}")


@caso("(y) SubagentStop dev BLOQUEADO / tipo alheio -> sem pendência")
def _y():
    roda(sub_stop(cerca({"status": "BLOQUEADO", "arquivos_alterados": ["src/A.tsx"],
                         "comandos_para_subir": ["pnpm dev"], "pendencias": ["x"]})))
    roda(sub_stop(cerca(ENTREGA_UI), tipo="general-purpose"))
    roda(sub_stop(cerca(ENTREGA_UI), tipo="outro:dev"))
    ok(not pendente(), f"criou pendência indevida: {entregas()!r}")


@caso("(z) SubagentStop repetido deduplica; retomado com contrato troca a entrega")
def _z():
    for _ in range(3):
        roda(sub_stop(cerca(ENTREGA_UI)))
    ok(len(entregas()) == 1, f"duplicou: {entregas()!r}")
    roda(sub_stop("esperando o filho", agent_id="dev2",
                  briefing="mexer em src/pages/Login.tsx"))
    ok(len(entregas()) == 2 and "Login.tsx" in entregas()[1]["arquivos"][0],
       f"fallback pelo transcript não anotou: {entregas()!r}")
    roda(sub_stop(cerca({"status": "OK", "arquivos_alterados": ["api/routes/users.ts"],
                         "comandos_para_subir": [], "resumo": "rota"}), agent_id="dev2"))
    roda(sub_stop("texto solto depois", agent_id="dev2"))
    e = entregas()
    ok(len(e) == 2 and e[1]["modo"] == "contrato", f"não trocou nem manteve o contrato: {e!r}")


@caso("(aa) tester PASSOU remove a entrega citada no briefing; sem citação, a mais antiga")
def _aa():
    roda(sub_stop(cerca(ENTREGA_UI), agent_id="devA"))
    roda(sub_stop(cerca({"status": "OK", "arquivos_alterados": ["backend/api/routes/users.ts"],
                         "comandos_para_subir": ["pnpm start"], "resumo": "rota"}),
                  agent_id="devB"))
    passou = cerca(VEREDITO | {"veredito": "PASSOU"})
    roda(sub_stop(passou, tipo="forge:tester", agent_id="t1",
                  briefing="valide a rota em api/routes/users.ts com curl"))
    roda(sub_stop(passou, tipo="forge:tester", agent_id="t1",
                  briefing="valide a rota em api/routes/users.ts com curl"))
    e = entregas()
    ok([x["agent_id"] for x in e] == ["devA"], f"removeu a entrega errada ou duas: {e!r}")
    roda(sub_stop(passou, tipo="forge:tester", agent_id="t2", briefing="valide tudo"))
    ok(not pendente(), "PASSOU sem citação não removeu a mais antiga")


@caso("(ab) tester FALHOU mantém a pendência e o Stop cita a falha")
def _ab():
    roda(sub_stop(cerca(ENTREGA_UI)))
    roda(sub_stop(cerca(VEREDITO | {"veredito": "FALHOU",
                                    "recomendacao_para_dev": "conter o botão"}),
                  tipo="forge:tester", agent_id="t1"))
    ok(len(entregas()) == 1, "FALHOU limpou a pendência")
    razao = bloqueio(roda(stop())[1])
    ok(razao and "FALHOU" in razao and "conter o botão" in razao, f"{razao!r}")


@caso("(ac) Stop bloqueia com pendência; libera sem ela, com stop_hook_active e já cobrada")
def _ac():
    rc, out, _ = roda(stop())
    ok(rc == 0 and out.strip() == "", f"sem pendência deveria liberar: {out!r}")
    roda(sub_stop(cerca(ENTREGA_UI)))
    rc, out, _ = roda(stop(stop_hook_active=True))
    ok(rc == 0 and out.strip() == "", f"stop_hook_active deveria liberar: {out!r}")
    em_voo = [{"id": "t", "type": "subagent", "status": "running", "agent_type": "forge:dev"}]
    ok(roda(stop(background_tasks=em_voo))[1].strip() == "", "bloqueou com dev em voo")
    razao = bloqueio(roda(stop())[1])
    ok(razao and "modo browser" in razao and "Card.tsx" in razao, f"não bloqueou: {razao!r}")
    ok("forge:tester" in razao and "usuário" in razao, f"razão incompleta: {razao!r}")
    ok(roda(stop())[1].strip() == "", "cobrou a mesma entrega duas vezes")
    ok(pendente(), "o Stop não pode limpar a pendência")


@caso("(ad) async_launched de tester na raiz marca andamento; SubagentStop do tester limpa")
def _ad():
    roda(sub_stop(cerca(ENTREGA_UI)))
    rc, out, _ = roda(tester_lancado(agent_id="sub1"))
    ok(rc == 0 and out.strip() == "", "aninhado deveria ficar calado")
    ok(not os.path.isfile(os.path.join(ESTADO[0], "tester-em-andamento")), "aninhado marcou")
    rc, out, _ = roda(tester_lancado())
    ok(rc == 0 and out.strip() == "", f"lançamento deveria ser silencioso: {out!r}")
    ok(roda(stop())[1].strip() == "", "bloqueou com tester em andamento")
    roda(sub_stop(cerca(VEREDITO | {"veredito": "BLOQUEADO"}), tipo="forge:tester",
                  agent_id="t1"))
    ok(pendente(), "BLOQUEADO aprovou por engano")
    razao = bloqueio(roda(stop())[1])
    ok(razao and "BLOQUEADO" in razao, f"tester terminou e o Stop não voltou a cobrar: {razao!r}")


def main():
    falhas = 0
    for nome, fn in CASOS:
        ESTADO[0] = tempfile.mkdtemp(prefix="forge-require-tester-")
        try:
            fn()
        except Exception as e:
            falhas += 1
            print(f"FALHOU  {nome}\n        {type(e).__name__}: {e}")
        else:
            print(f"ok      {nome}")
        finally:
            shutil.rmtree(ESTADO[0], ignore_errors=True)
    total = len(CASOS)
    print(f"\n{total - falhas}/{total} casos passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
