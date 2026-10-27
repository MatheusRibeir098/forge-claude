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


def roda(cwd, comando, agent_type=None):
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": cwd,
               "tool_input": {"command": comando}}
    if agent_type:
        payload["agent_type"] = agent_type
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True)
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
