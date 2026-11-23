#!/usr/bin/env python3
"""Testes do deny-orchestrator-code-edits.sh — o hook que impõe o Invariante 1
(o orquestrador não escreve código de produto).

POR QUE ESTA SUÍTE EXISTE: este é o hook mais importante do plugin. Se ele barrasse o
`.claude/settings.json` que o próprio `/forge:setup` precisa criar, o agente poderia contornar
escrevendo por `Bash` — furando o invariante por um caminho que o hook não vê. A suíte fixa
essas bordas (o que o setup pode criar, o que continua barrado) para que uma regressão apareça
antes do usuário.
"""
import json, os, shutil, subprocess, sys, tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                    "deny-orchestrator-code-edits.sh")
casos, falhas = [], []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn))
        return fn
    return deco


def roda(cwd, file_path, agent_type=None, tool="Write", env=None):
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": cwd,
               "tool_input": {"file_path": os.path.join(cwd, file_path)}}
    if agent_type:
        payload["agent_type"] = agent_type
    r = subprocess.run(["bash", HOOK], input=json.dumps(payload), capture_output=True,
                       text=True, env={**os.environ, **(env or {})})
    return '"deny"' in r.stdout


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def fabrica():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "projects"))
    os.makedirs(os.path.join(d, "templates"))
    open(os.path.join(d, "templates", "prompt.template.md"), "w").close()
    return d


def repo():
    return tempfile.mkdtemp()


@caso("(a) fábrica: código de produto é negado")
def _a():
    d = fabrica()
    try:
        ok(roda(d, "projects/x/src/app.tsx"), "deveria negar .tsx")
        ok(roda(d, "src/app.py"), "deveria negar .py")
    finally:
        shutil.rmtree(d)


@caso("(b) fábrica: arquivos de controle são liberados")
def _b():
    d = fabrica()
    try:
        for f in ("projects/x/.forge/tasks.md", "projects/x/prompt.md", "CLAUDE.md",
                  "templates/.npmrc"):
            ok(not roda(d, f), f"deveria liberar {f}")
    finally:
        shutil.rmtree(d)


@caso("(c) o /forge:setup consegue criar o que precisa, na raiz")
def _c():
    for mk in (fabrica, repo):
        d = mk()
        try:
            for f in (".claude/settings.json", ".claude/settings.local.json", ".gitignore"):
                ok(not roda(d, f), f"o setup precisa escrever {f} em {mk.__name__}")
        finally:
            shutil.rmtree(d)
    d = fabrica()
    try:
        ok(not roda(d, "projects/.gitkeep"), "o setup precisa criar projects/.gitkeep")
    finally:
        shutil.rmtree(d)


@caso("(d) a exceção do setup não vaza para fora da raiz")
def _d():
    d = fabrica()
    try:
        ok(roda(d, "projects/x/.claude/settings.json"),
           "config de projeto filho não pode ser escrita pelo orquestrador")
        ok(roda(d, "sub/.gitignore"), ".gitignore fora da raiz não é exceção")
    finally:
        shutil.rmtree(d)


@caso("(d2) fábrica nova criada em subcaminho do repo atual: setup consegue escrever")
def _d2():
    d = repo()
    try:
        for f in ("forge/.gitignore", "forge/.claude/settings.json",
                  "forge/.claude/settings.local.json", "forge/projects/.gitkeep",
                  "forge/templates/.npmrc"):
            ok(not roda(d, f), f"o setup precisa criar {f} numa fábrica nova em subcaminho")
    finally:
        shutil.rmtree(d)


@caso("(e) repo atual: .forge/ e markdown liberados, código negado")
def _e():
    d = repo()
    try:
        ok(not roda(d, ".forge/tasks.md"), "deveria liberar .forge/")
        ok(not roda(d, "README.md"), "deveria liberar markdown")
        ok(roda(d, "src/index.ts"), "deveria negar código")
    finally:
        shutil.rmtree(d)


@caso("(f) subagente escreve o que quiser")
def _f():
    for mk in (fabrica, repo):
        d = mk()
        try:
            ok(not roda(d, "src/app.py", agent_type="dev"), "dev pode escrever código")
            ok(not roda(d, "e2e/spec.ts", agent_type="tester"), "tester pode escrever spec")
        finally:
            shutil.rmtree(d)


@caso("(h) fora da raiz é livre (scratchpad, /tmp), nos dois modos")
def _h():
    for mk in (fabrica, repo):
        d = mk()
        try:
            for f in ("/tmp/claude-1000/x/scratchpad/c.py", "/tmp/solto.ts"):
                ok(not roda(d, f), f"deveria liberar {f} em {mk.__name__}")
        finally:
            shutil.rmtree(d)


@caso("(i) `..` que volta para dentro da raiz continua barrado")
def _i():
    for mk in (fabrica, repo):
        d = mk()
        try:
            volta = os.path.join("/tmp", "..", d.lstrip("/"), "src", "a.ts")
            ok(roda(d, volta), f"deveria negar {volta} em {mk.__name__}")
        finally:
            shutil.rmtree(d)


@caso("(j) artefatos .log/.patch/.diff/.out/.txt liberados; requirements*.txt barrado")
def _j():
    for mk in (fabrica, repo):
        d = mk()
        try:
            for f in ("build.log", "src/d.patch", "x.diff", "out.txt", "a/b/saida.out"):
                ok(not roda(d, f), f"deveria liberar {f} em {mk.__name__}")
            for f in ("requirements.txt", "requirements-dev.txt", "src/a.ts"):
                ok(roda(d, f), f"deveria negar {f} em {mk.__name__}")
        finally:
            shutil.rmtree(d)


@caso("(k) fábrica: projects/x/src/a.ts barrado, projects/x/.forge/estado.json liberado")
def _k():
    d = fabrica()
    try:
        ok(roda(d, "projects/x/src/a.ts"), "deveria negar código de projeto")
        ok(not roda(d, "projects/x/.forge/estado.json"), "deveria liberar .forge/")
    finally:
        shutil.rmtree(d)


# --- modo "projeto da fábrica": sessão aberta em <fábrica>/projects/<nome> -------------------
# A fábrica e o HOME falso ficam em /var/tmp (fora de /tmp) para que a exceção de /tmp não
# esconda a negação; um caso à parte cobre a fábrica dentro de /tmp.
BASE_FORA_DO_TMP = "/var/tmp" if os.path.isdir("/var/tmp") else None


def mundo(fn, base=BASE_FORA_DO_TMP):
    """Fábrica com projects/x e projects/y, HOME falso com ~/.claude e ~/.claude-empresa."""
    d = tempfile.mkdtemp(dir=base)
    home = tempfile.mkdtemp(dir=BASE_FORA_DO_TMP)
    try:
        os.makedirs(os.path.join(d, "projects"))
        os.makedirs(os.path.join(d, "templates"))
        open(os.path.join(d, "templates", "prompt.template.md"), "w").close()
        for projeto in ("x", "y"):
            os.makedirs(os.path.join(d, "projects", projeto, "sub"))
        for pasta in (".claude/projects/-x/memory", ".claude-empresa/plans", ".cache/algo"):
            os.makedirs(os.path.join(home, pasta))
        fn(d, home, {"HOME": home})
    finally:
        shutil.rmtree(d)
        shutil.rmtree(home)


@caso("(p1) projeto da fábrica, orquestrador: código negado, controle liberado")
def _p1():
    def corpo(d, home, env):
        x = os.path.join(d, "projects", "x")
        ok(roda(x, "src/a.ts", env=env), "deveria negar código em projects/x")
        for f in (".forge/progress.md", "README.md", "prompt.md", "build.log", ".gitignore",
                  ".claude/settings.json"):
            ok(not roda(x, f, env=env), f"deveria liberar {f} em projects/x")
        ok(roda(x, "requirements.txt", env=env), "requirements.txt é código")
        ok(roda(x, "sub/.gitignore", env=env), "config do setup só na raiz do projeto")
    mundo(corpo)


@caso("(p2) projeto da fábrica, orquestrador: fora do projeto negado, inclusive .md/.txt")
def _p2():
    def corpo(d, home, env):
        x = os.path.join(d, "projects", "x")
        for f in ("../y/README.md", "../y/src/a.ts", "../y/.forge/progress.md", "../y/saida.txt",
                  "../../CLAUDE.md", "../../templates/x.md", "../../plugins/a.py"):
            ok(roda(x, f, env=env), f"deveria negar {f} (fora de projects/x)")
        for f in (os.path.join(home, ".cache", "algo", "a.md"), os.path.join(home, "x.md")):
            ok(roda(x, f, env=env), f"deveria negar {f} (HOME fora de ~/.claude*)")
    mundo(corpo)


@caso("(p3) projeto da fábrica: /tmp, $TMPDIR e ~/.claude* liberados fora do projeto")
def _p3():
    def corpo(d, home, env):
        x = os.path.join(d, "projects", "x")
        tmpdir = tempfile.mkdtemp(dir=BASE_FORA_DO_TMP)
        try:
            for ag in (None, "dev"):
                for f in ("/tmp/forge-teste-livre/a.ts", os.path.join(
                        home, ".claude/projects/-x/memory/a.md"),
                        os.path.join(home, ".claude-empresa/plans/p.md")):
                    ok(not roda(x, f, agent_type=ag, env=env), f"deveria liberar {f} ({ag})")
                ok(roda(x, os.path.join(tmpdir, "a.ts"), agent_type=ag, env=env),
                   f"sem TMPDIR definido, {tmpdir} está fora ({ag})")
                ok(not roda(x, os.path.join(tmpdir, "a.ts"), agent_type=ag,
                            env={**env, "TMPDIR": tmpdir}), f"com TMPDIR, {tmpdir} é livre ({ag})")
        finally:
            shutil.rmtree(tmpdir)
    mundo(corpo)


@caso("(p4) projeto da fábrica, subagente: livre no projeto, negado fora")
def _p4():
    def corpo(d, home, env):
        x = os.path.join(d, "projects", "x")
        for ag in ("dev", "tester"):
            ok(not roda(x, "src/a.ts", agent_type=ag, env=env), f"{ag} escreve no projeto")
            ok(roda(x, "../y/src/a.ts", agent_type=ag, env=env), f"{ag} não escreve em y")
            ok(roda(x, "../y/README.md", agent_type=ag, env=env), f"{ag} não escreve .md de y")
            ok(roda(x, "../../CLAUDE.md", agent_type=ag, env=env), f"{ag} não escreve na fábrica")
    mundo(corpo)


@caso("(p5) sessão numa subpasta do projeto: contenção pela raiz do projeto")
def _p5():
    def corpo(d, home, env):
        sub = os.path.join(d, "projects", "x", "sub")
        ok(roda(sub, "../src/a.ts", env=env), "orquestrador: código no projeto segue negado")
        ok(not roda(sub, "../.forge/progress.md", env=env), ".forge na raiz de x é liberado")
        ok(not roda(sub, "notas.md", env=env), "markdown na subpasta é liberado")
        ok(roda(sub, "../../y/README.md", env=env), "y está fora do projeto")
        ok(not roda(sub, "../src/a.ts", agent_type="dev", env=env), "dev escreve em x")
        ok(roda(sub, "../../y/a.ts", agent_type="dev", env=env), "dev não escreve em y")
    mundo(corpo)


@caso("(p6) `..` e symlink que saem do projeto são negados")
def _p6():
    def corpo(d, home, env):
        x = os.path.join(d, "projects", "x")
        y = os.path.join(d, "projects", "y")
        os.symlink(y, os.path.join(x, "atalho"))
        os.symlink("/tmp", os.path.join(x, "para-tmp"))
        for ag in (None, "dev"):
            ok(roda(x, os.path.join(x, "src", "..", "..", "y", "README.md"), agent_type=ag,
                    env=env), f"`..` que sai de x deve negar ({ag})")
            ok(roda(x, "atalho/README.md", agent_type=ag, env=env),
               f"symlink para y deve negar ({ag})")
            ok(not roda(x, "para-tmp/a.ts", agent_type=ag, env=env),
               f"symlink para /tmp cai na exceção do /tmp ({ag})")
    mundo(corpo)


@caso("(p7) fábrica dentro de /tmp: a exceção de /tmp não vaza para a fábrica")
def _p7():
    def corpo(d, home, env):
        x = os.path.join(d, "projects", "x")
        ok(roda(x, "../y/README.md", env=env), "y continua fora do projeto")
        ok(roda(x, "../../CLAUDE.md", agent_type="dev", env=env), "fábrica não é /tmp livre")
        ok(not roda(x, "/tmp/forge-teste-livre/a.ts", env=env), "o resto de /tmp segue livre")
    mundo(corpo, base=None)


@caso("(p8) mensagem da contenção cita projeto, caminho e a fábrica; código cita o dev")
def _p8():
    def corpo(d, home, env):
        x = os.path.join(d, "projects", "x")
        payload = {"tool_name": "Write", "cwd": x,
                   "tool_input": {"file_path": os.path.join(d, "projects", "y", "README.md")}}
        r = subprocess.run(["bash", HOOK], input=json.dumps(payload), capture_output=True,
                           text=True, env={**os.environ, **env})
        razao = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        for trecho in ("fora da pasta do projeto", "'x'", os.path.realpath(x), "/tmp",
                       "~/.claude*", os.path.realpath(d), "raiz da fábrica"):
            ok(trecho in razao, f"faltou {trecho!r} em: {razao}")
        payload["tool_input"]["file_path"] = os.path.join(x, "src", "a.ts")
        r = subprocess.run(["bash", HOOK], input=json.dumps(payload), capture_output=True,
                           text=True, env={**os.environ, **env})
        razao = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        ok("subagente dev" in razao and "projeto da fábrica" in razao, razao)
    mundo(corpo)


@caso("(p9) regressão: fábrica e repo atual seguem iguais (subagente livre, fora da raiz livre)")
def _p9():
    for mk in (fabrica, repo):
        d = mk()
        try:
            ok(not roda(d, "../outro/src/a.ts"), f"fora da raiz é livre em {mk.__name__}")
            ok(not roda(d, "src/a.ts", agent_type="dev"), f"dev livre em {mk.__name__}")
            ok(roda(d, "src/a.ts"), f"código negado em {mk.__name__}")
        finally:
            shutil.rmtree(d)
    d = fabrica()  # sessão em projects/y de uma fábrica SEM templates/prompt.template.md
    try:
        os.remove(os.path.join(d, "templates", "prompt.template.md"))
        y = os.path.join(d, "projects", "y")
        os.makedirs(y)
        ok(not roda(y, "../z/src/a.ts"), "projects/ sem ser fábrica = repo atual (fora livre)")
    finally:
        shutil.rmtree(d)


@caso("(g) payload ilegível não bloqueia nada")
def _g():
    r = subprocess.run(["bash", HOOK], input="isto não é json",
                       capture_output=True, text=True)
    ok(r.returncode == 0 and '"deny"' not in r.stdout, "payload ruim deveria passar calado")


if __name__ == "__main__":
    for nome, fn in casos:
        try:
            fn()
            print(f"ok      {nome}")
        except Exception as e:
            falhas.append(nome)
            print(f"FALHOU  {nome}\n        {type(e).__name__}: {e}")
    print(f"\n{len(casos) - len(falhas)}/{len(casos)} casos passaram")
    sys.exit(1 if falhas else 0)
