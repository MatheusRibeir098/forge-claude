#!/usr/bin/env python3
"""Testes do deny-orchestrator-code-edits.sh — o hook que impõe o Invariante 1
(o orquestrador não escreve código de produto).

POR QUE ESTA SUÍTE EXISTE: este é o hook mais importante do plugin e era o único sem teste.
A lacuna apareceu num teste de instalação real: o hook barrava o `.claude/settings.json` que o
próprio `/forge:setup` precisa criar, e o agente contornou escrevendo por `Bash` — furando o
invariante por um caminho que o hook não vê. Sem suíte, nada disso aparecia antes do usuário.
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


def roda(cwd, file_path, agent_type=None, tool="Write"):
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": cwd,
               "tool_input": {"file_path": os.path.join(cwd, file_path)}}
    if agent_type:
        payload["agent_type"] = agent_type
    r = subprocess.run(["bash", HOOK], input=json.dumps(payload),
                       capture_output=True, text=True)
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
