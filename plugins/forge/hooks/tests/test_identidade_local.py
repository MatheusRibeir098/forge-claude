#!/usr/bin/env python3
"""Testes do git-identidade-local.py — `git commit` exige identidade git LOCAL.

    python3 plugins/forge/hooks/tests/test_identidade_local.py

Usa repositórios temporários criados com `git init`. A config global da máquina é irrelevante:
o hook só olha `git config --local`.
"""
import json, os, shutil, subprocess, sys, tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "git-identidade-local.py")
casos, falhas = [], []
ENV_LIMPO = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def caso(nome):
    def deco(fn):
        casos.append((nome, fn))
        return fn
    return deco


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def roda(cwd, comando, agent_type=None):
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": cwd,
               "tool_input": {"command": comando}}
    if agent_type:
        payload["agent_type"] = agent_type
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True)
    ok(r.returncode == 0, f"exit {r.returncode}: {r.stderr}")
    return '"deny"' in r.stdout, r.stdout


def novo_repo(com_email):
    d = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q", d], check=True, env=ENV_LIMPO)
    if com_email:
        subprocess.run(["git", "-C", d, "config", "--local", "user.email", "a@b.c"],
                       check=True, env=ENV_LIMPO)
    return d


def com_repos(fn):
    sem, com, fora = novo_repo(False), novo_repo(True), tempfile.mkdtemp()
    try:
        fn(sem, com, fora)
    finally:
        for d in (sem, com, fora):
            shutil.rmtree(d)


@caso("sem e-mail local, `git commit` é negado (e a mensagem orienta)")
def _nega():
    def corpo(sem, com, fora):
        negou, saida = roda(sem, "git commit -m x")
        ok(negou, "deveria negar")
        razao = json.loads(saida)["hookSpecificOutput"]["permissionDecisionReason"]
        for trecho in ("identidade git local", "git-profiles", "git config --local user.name",
                       "git config --local user.email", "identidade global"):
            ok(trecho in razao, f"faltou {trecho!r} em: {razao}")
    com_repos(corpo)


@caso("com e-mail local, passa")
def _passa():
    def corpo(sem, com, fora):
        ok(not roda(com, "git commit -m x")[0], "deveria passar")
        ok(not roda(com, "git add -A && git commit -am x")[0], "deveria passar")
    com_repos(corpo)


@caso("`git -C <repo> commit` usa o repo do -C, não o cwd")
def _dash_c():
    def corpo(sem, com, fora):
        ok(roda(fora, f"git -C {sem} commit -m x")[0], "-C sem e-mail deveria negar")
        ok(not roda(fora, f"git -C {com} commit -m x")[0], "-C com e-mail deveria passar")
        ok(not roda(sem, f"git -C {com} commit -m x")[0], "-C vence o cwd do payload")
    com_repos(corpo)


@caso("`cd <repo> && git commit` usa o repo do cd")
def _cd():
    def corpo(sem, com, fora):
        ok(roda(fora, f"cd {sem} && git commit -m x")[0], "cd em repo sem e-mail deveria negar")
        ok(not roda(fora, f"cd {com} && git commit -m x")[0], "cd em repo com e-mail passa")
        ok(not roda(sem, f"cd {com} && git commit -m x")[0], "cd vence o cwd do payload")
    com_repos(corpo)


@caso('`grep "git commit"` não é invocação')
def _grep():
    def corpo(sem, com, fora):
        ok(not roda(sem, 'grep "git commit" -r .')[0], "aspas não são invocação")
        ok(not roda(sem, "echo 'git commit -m x'")[0], "echo entre aspas não é invocação")
        ok(not roda(sem, "git status && git log")[0], "outros subcomandos passam")
    com_repos(corpo)


@caso("silêncio: fora de repo, diretório inexistente, comando ilegível")
def _silencio():
    def corpo(sem, com, fora):
        ok(not roda(fora, "git commit -m x")[0], "fora de repo: silêncio")
        ok(not roda(fora, "git -C /nao/existe/mesmo commit -m x")[0], "dir inexistente: silêncio")
        ok(not roda(sem, "git commit -m 'aspas abertas")[0], "ilegível: silêncio")
    com_repos(corpo)


@caso("vale também para subagentes")
def _subagente():
    def corpo(sem, com, fora):
        ok(roda(sem, "git commit -m x", agent_type="dev")[0], "dev sem e-mail local: nega")
        ok(not roda(com, "git commit -m x", agent_type="dev")[0], "dev com e-mail local: passa")
    com_repos(corpo)


@caso("identidade explícita no comando conta; heredoc de mensagem não confunde")
def _explicita():
    def corpo(sem, com, fora):
        ok(not roda(sem, "git -c user.email=x@y.z commit -m x")[0], "-c user.email passa")
        ok(not roda(sem, "GIT_AUTHOR_EMAIL=x@y.z git commit -m x")[0], "GIT_AUTHOR_EMAIL passa")
        msg = "git commit -m \"$(cat <<'EOF'\nfeat: x\nEOF\n)\""
        ok(roda(sem, msg)[0], "commit com heredoc em repo sem e-mail: nega")
        ok(not roda(com, msg)[0], "commit com heredoc em repo com e-mail: passa")
    com_repos(corpo)


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
