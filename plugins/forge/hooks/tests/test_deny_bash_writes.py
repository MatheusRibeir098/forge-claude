#!/usr/bin/env python3
"""Testes do deny-orchestrator-bash-writes.py — escrita de código do orquestrador via Bash.

POR QUE EXISTE: depois de ter um Write barrado, o orquestrador poderia regravar o mesmo
conteúdo com `cat > x <<EOF`, `tee` ou `sed -i`. Este hook fecha esse atalho, com a MESMA regra
de caminho do hook de Write|Edit (lib/decisao_escrita.py).

    python3 plugins/forge/hooks/tests/test_deny_bash_writes.py
"""
import json, os, shutil, subprocess, sys, tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                    "deny-orchestrator-bash-writes.py")
casos, falhas = [], []


def caso(nome):
    def deco(fn):
        casos.append((nome, fn))
        return fn
    return deco


def roda(cwd, comando, agent_type=None, env=None):
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": cwd,
               "tool_input": {"command": comando}}
    if agent_type:
        payload["agent_type"] = agent_type
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True,
                       text=True, env={**os.environ, **(env or {})})
    ok(r.returncode == 0, f"exit {r.returncode}: {r.stderr}")
    return '"deny"' in r.stdout, r.stdout


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def com_repo(fn):
    d = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(d, ".forge"))
        os.makedirs(os.path.join(d, "src"))
        fn(d)
    finally:
        shutil.rmtree(d)


NEGADOS = [
    "cat > src/app.ts <<EOF\nconsole.log(1)\nEOF",
    "tee hooks/x.py",
    "echo x | tee -a src/a.ts",
    "sed -i s/a/b/ src/a.ts",
    "sed -i.bak -e 's/a/b/' src/a.ts",
    "perl -pi -e 's/a/b/' src/a.ts",
    "echo x >> src/a.ts",
    "echo x > requirements.txt",
    "cp /tmp/a.py plugins/forge/hooks/a.py",
    "cmd &> out.py",
    "cp /tmp/novo.ts src/a.ts",
    "mv rascunho src/a.ts",
    "install -m 755 build.sh bin/run",
    "cd src && echo x > a.ts",
    "echo $(cat > src/a.ts)",
    "cat <<'EOF' > src/a.ts\n\"aspas soltas\nEOF",
]

LIBERADOS = [
    "echo x > .forge/notas.md",
    "cmd 2>&1",
    "cmd > /dev/null",
    "cmd >/dev/null 2>&1",
    "cmd &> /dev/null",
    "cmd 2>/dev/null",
    'grep "cat > a.ts" -r .',
    'echo "tee src/a.ts"',
    "grep '>' src/a.ts",
    'grep ">" src/a.ts',
    "sed s/a/b/ src/a.ts",
    "sed -n 1,5p src/a.ts",
    "cat src/a.ts | grep x",
    "echo x > README.md",
    "cp a.ts .forge/a.md",
    "cp a.md docs/",
    "mv .forge/a.md .forge/b.md",
    "cmd > $SAIDA",
    "echo x > /tmp/claude-1000/x/scratchpad/a.py",
    "git diff > /tmp/d.patch",
    "pnpm build 2>&1 | tee build.log",
    "echo x > out.txt",
    "echo x > notas.diff",
    "echo x > saida.out",
    "tee .forge/log.md",
    "git commit -m \"$(cat <<'EOF'\nfeat: x > y\nEOF\n)\"",
    "cd .forge && echo x > notas.md",
    "",
    "echo 'aspas desbalanceadas",
]


@caso("nega na principal: escrita de código por Bash")
def _nega():
    def corpo(d):
        for c in NEGADOS:
            ok(roda(d, c)[0], f"deveria negar: {c!r}")
    com_repo(corpo)


@caso("libera na principal: .forge, descritores, /dev/null, aspas, alvos liberados")
def _libera():
    def corpo(d):
        for c in LIBERADOS:
            negou, saida = roda(d, c)
            ok(not negou, f"deveria liberar: {c!r}\n{saida}")
    com_repo(corpo)


@caso("libera no subagente: os mesmos comandos negados na principal")
def _subagente():
    def corpo(d):
        for agente in ("dev", "tester"):
            for c in NEGADOS:
                ok(not roda(d, c, agent_type=agente)[0], f"{agente} pode escrever: {c!r}")
    com_repo(corpo)


@caso("a mensagem de negação cita Bash, dev e a proibição de contornar")
def _mensagem():
    def corpo(d):
        _, saida = roda(d, "tee src/a.ts")
        razao = json.loads(saida)["hookSpecificOutput"]["permissionDecisionReason"]
        for trecho in ("também via Bash", "subagente dev", "Contornar uma negação anterior"):
            ok(trecho in razao, f"faltou {trecho!r} em: {razao}")
    com_repo(corpo)


@caso("mesma regra do hook de Write|Edit: fábrica libera */templates/* e nega o resto")
def _fabrica():
    d = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(d, "projects"))
        os.makedirs(os.path.join(d, "templates"))
        open(os.path.join(d, "templates", "prompt.template.md"), "w").close()
        ok(not roda(d, "echo x > templates/foo.ts")[0], "fábrica libera templates/")
        ok(not roda(d, "echo x > projects/p/.forge/t.json")[0], "fábrica libera .forge/")
        ok(roda(d, "echo x > projects/p/src/a.ts")[0], "fábrica nega código")
        ok(not roda(d, "git diff > /tmp/d.patch")[0], "fábrica libera fora da raiz")
        ok(not roda(d, "echo x > projects/p/build.log")[0], "fábrica libera *.log")
    finally:
        shutil.rmtree(d)


@caso("fora da raiz é livre, mas `..` que volta para dentro da raiz continua barrado")
def _fora_da_raiz():
    def corpo(d):
        ok(not roda(d, "echo x > /tmp/solto.ts")[0], "/tmp está fora da raiz")
        volta = os.path.join("/tmp", "..", d.lstrip("/"), "src", "a.ts")
        ok(roda(d, f"echo x > {volta}")[0], f"`..` de volta à raiz deveria negar: {volta}")
    com_repo(corpo)


@caso("symlink de fora apontando para dentro não engana; para fora é livre")
def _symlink():
    def corpo(d):
        fora = tempfile.mkdtemp()
        try:
            os.symlink(os.path.join(d, "src"), os.path.join(fora, "atalho"))
            ok(roda(d, f"echo x > {fora}/atalho/a.ts")[0], "symlink para dentro deveria negar")
            os.symlink(fora, os.path.join(d, "src", "saida"))
            ok(not roda(d, "echo x > src/saida/a.ts")[0], "symlink para fora é fora da raiz")
        finally:
            shutil.rmtree(fora)
    com_repo(corpo)


# --- modo "projeto da fábrica": sessão aberta em <fábrica>/projects/<nome> -------------------
# Fábrica e HOME falso em /var/tmp (fora de /tmp), para a exceção de /tmp não esconder a negação.
BASE_FORA_DO_TMP = "/var/tmp" if os.path.isdir("/var/tmp") else None


def mundo(fn, base=BASE_FORA_DO_TMP):
    d = tempfile.mkdtemp(dir=base)
    home = tempfile.mkdtemp(dir=BASE_FORA_DO_TMP)
    try:
        os.makedirs(os.path.join(d, "projects"))
        os.makedirs(os.path.join(d, "templates"))
        open(os.path.join(d, "templates", "prompt.template.md"), "w").close()
        for projeto in ("x", "y"):
            os.makedirs(os.path.join(d, "projects", projeto, "sub"))
        for pasta in (".claude/projects/-x/memory", ".claude-empresa/plans", ".cache"):
            os.makedirs(os.path.join(home, pasta))
        fn(os.path.join(d, "projects", "x"), d, home, {"HOME": home})
    finally:
        shutil.rmtree(d)
        shutil.rmtree(home)


@caso("projeto da fábrica, principal: código negado, controle liberado, fora do projeto negado")
def _projeto_principal():
    def corpo(x, d, home, env):
        for c in ("echo x > src/a.ts", "tee src/a.ts", "sed -i s/a/b/ src/a.ts",
                  "cp /tmp/a.ts src/a.ts", "echo x > ../y/README.md", "echo x > ../y/a.ts",
                  f"echo x >> {d}/CLAUDE.md", f"cp a.md {d}/templates/", "mv a.md ../y/b.md",
                  f"echo x > {home}/.cache/a.md", "echo x > ../y/saida.txt"):
            ok(roda(x, c, env=env)[0], f"deveria negar: {c!r}")
        for c in (
                "echo x > .forge/progress.md", "echo x > README.md", "echo x > build.log",
                "cmd > /dev/null", "echo x > /tmp/forge-teste-livre/a.ts",
                f"echo x > {home}/.claude/projects/-x/memory/a.md",
                f"echo x > {home}/.claude-empresa/plans/p.md", "cd sub && echo x > notas.md",
                "git diff > /tmp/d.patch"):
            negou, saida = roda(x, c, env=env)
            ok(not negou, f"deveria liberar: {c!r}\n{saida}")
    mundo(corpo)


@caso("projeto da fábrica, subagente: livre no projeto, negado fora (exceto /tmp e ~/.claude*)")
def _projeto_subagente():
    def corpo(x, d, home, env):
        for ag in ("dev", "tester"):
            for c in ("echo x > src/a.ts", "sed -i s/a/b/ src/a.ts", "tee e2e/a.spec.ts",
                      "echo x > /tmp/a", f"echo x > {home}/.claude/a.md"):
                ok(not roda(x, c, agent_type=ag, env=env)[0], f"{ag} pode: {c!r}")
            for c in ("echo x > ../y/src/a.ts", "echo x > ../y/README.md", f"tee {d}/CLAUDE.md",
                      "cp src/a.ts ../y/a.ts", "cd .. && echo x > y/a.ts"):
                ok(roda(x, c, agent_type=ag, env=env)[0], f"{ag} não pode: {c!r}")
    mundo(corpo)


@caso("projeto da fábrica: sessão em subpasta, `..` e symlink saindo do projeto")
def _projeto_sub_e_saidas():
    def corpo(x, d, home, env):
        sub = os.path.join(x, "sub")
        ok(roda(sub, "echo x > ../../y/a.md", env=env)[0], "sub: y está fora do projeto x")
        ok(roda(sub, "echo x > ../src/a.ts", env=env)[0], "sub: código em x negado")
        ok(not roda(sub, "echo x > ../.forge/p.md", env=env)[0], "sub: .forge de x liberado")
        ok(not roda(sub, "echo x > ../src/a.ts", agent_type="dev", env=env)[0], "sub: dev em x")
        os.symlink(os.path.join(d, "projects", "y"), os.path.join(x, "atalho"))
        for ag in (None, "dev"):
            ok(roda(x, "echo x > atalho/README.md", agent_type=ag, env=env)[0],
               f"symlink para y negado ({ag})")
            ok(roda(x, "echo x > src/../../y/README.md", agent_type=ag, env=env)[0],
               f"`..` para y negado ({ag})")
    mundo(corpo)


@caso("projeto da fábrica: mensagem da contenção cita projeto, caminho, fábrica e Bash")
def _projeto_mensagem():
    def corpo(x, d, home, env):
        _, saida = roda(x, "echo x > ../y/README.md", env=env)
        razao = json.loads(saida)["hookSpecificOutput"]["permissionDecisionReason"]
        for trecho in ("fora da pasta do projeto", "Bash", "'x'", os.path.realpath(x),
                       os.path.realpath(d), "/tmp", "~/.claude*"):
            ok(trecho in razao, f"faltou {trecho!r} em: {razao}")
        _, saida = roda(x, "echo x > src/a.ts", env=env)
        razao = json.loads(saida)["hookSpecificOutput"]["permissionDecisionReason"]
        ok("subagente dev" in razao and "Contornar uma negação" in razao, razao)
    mundo(corpo)


@caso("fábrica dentro de /tmp: a exceção de /tmp não vaza para a fábrica")
def _projeto_fabrica_em_tmp():
    def corpo(x, d, home, env):
        ok(roda(x, "echo x > ../y/README.md", agent_type="dev", env=env)[0], "y segue fora")
        ok(not roda(x, "echo x > /tmp/forge-teste-livre/a.ts", env=env)[0], "/tmp segue livre")
    mundo(corpo, base=None)


@caso("regressão: sessão em projects/ de repo sem ser fábrica segue como repo atual")
def _regressao_repo_atual():
    d = tempfile.mkdtemp()
    try:
        y = os.path.join(d, "projects", "y")
        os.makedirs(y)  # sem templates/prompt.template.md: não é fábrica
        ok(not roda(y, "echo x > ../z/a.ts")[0], "fora da raiz é livre no repo atual")
        ok(roda(y, "echo x > src/a.ts")[0], "código segue negado")
        ok(not roda(y, "echo x > src/a.ts", agent_type="dev")[0], "subagente livre")
    finally:
        shutil.rmtree(d)


@caso("payload ilegível não bloqueia nada")
def _ilegivel():
    r = subprocess.run([sys.executable, HOOK], input="isto não é json",
                       capture_output=True, text=True)
    ok(r.returncode == 0 and not r.stdout, "payload ruim deveria passar calado")


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
