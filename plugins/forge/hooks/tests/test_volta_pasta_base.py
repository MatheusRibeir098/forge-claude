#!/usr/bin/env python3
"""Testes do hook `volta-pasta-base.py` — só stdlib, sem dependência externa.

    python3 plugins/forge/hooks/tests/test_volta_pasta_base.py

Cada caso roda o hook como processo, com `CLAUDE_PROJECT_DIR` controlado pelo teste. O rtk é
sempre um binário falso (`FORGE_RTK_BIN`) para não depender do rtk da máquina.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.dirname(AQUI)
HOOK = os.path.join(HOOKS, "volta-pasta-base.py")
RTK_ROOT = os.path.join(HOOKS, "rtk-root.sh")

RAIZ = "/proj/base"
FORA = "/outra/pasta"

CASOS = []

FAKE_RTK = """#!/usr/bin/env python3
import json, sys
d = json.load(sys.stdin)
ti = dict(d["tool_input"], command="rtk " + d["tool_input"]["command"])
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
    "updatedInput": ti, "permissionDecision": "allow"}}))
"""


def caso(nome):
    def deco(fn):
        CASOS.append((nome, fn))
        return fn
    return deco


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def payload(tool_name="Bash", cwd=FORA, comando="ls -la", **extra):
    d = {"tool_name": tool_name, "cwd": cwd, "session_id": "s",
         "tool_input": {"command": comando, "description": "d"}}
    d.update(extra)
    return d


def roda(script, entrada, raiz=RAIZ, rtk_bin=None):
    env = dict(os.environ)
    env.pop("FORGE_VOLTA_COMPOSE", None)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if raiz is not None:
        env["CLAUDE_PROJECT_DIR"] = raiz
    env["FORGE_RTK_BIN"] = rtk_bin or "/nao/existe/rtk"
    bruto = entrada if isinstance(entrada, str) else json.dumps(entrada)
    cmd = ["python3", script] if script.endswith(".py") else ["bash", script]
    p = subprocess.run(cmd, input=bruto, env=env, capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout


def saida_json(stdout):
    return json.loads(stdout)["hookSpecificOutput"]


def rtk_falso(tmp):
    caminho = os.path.join(tmp, "rtk")
    with open(caminho, "w") as f:
        f.write(FAKE_RTK)
    os.chmod(caminho, os.stat(caminho).st_mode | stat.S_IXUSR)
    return caminho


@caso("cwd igual à raiz: sem saída")
def _(tmp):
    rc, out = roda(HOOK, payload(cwd=RAIZ))
    ok(rc == 0 and out == "", f"rc={rc} out={out!r}")


@caso("cwd igual à raiz com barra final e symlink: sem saída")
def _(tmp):
    real = os.path.join(tmp, "real")
    os.mkdir(real)
    link = os.path.join(tmp, "link")
    os.symlink(real, link)
    rc, out = roda(HOOK, payload(cwd=real + "/"), raiz=link)
    ok(rc == 0 and out == "", f"rc={rc} out={out!r}")


@caso("cwd diferente: comando reescrito com prefixo e systemMessage")
def _(tmp):
    rc, out = roda(HOOK, payload(comando="ls -la"))
    ok(rc == 0, f"rc={rc}")
    saida = saida_json(out)
    ok(saida["hookEventName"] == "PreToolUse", saida)
    ok(saida["updatedInput"]["command"] == f'cd "{RAIZ}" && ls -la', saida)
    ok(saida["updatedInput"]["description"] == "d", "campos do tool_input devem ser preservados")
    ok("permissionDecision" not in saida, "nunca devolve permissionDecision")
    msg = json.loads(out)["systemMessage"]
    ok(msg.startswith("[pasta base]") and FORA in msg and RAIZ in msg, msg)


@caso("raiz com caractere especial é escapada entre aspas")
def _(tmp):
    rc, out = roda(HOOK, payload(), raiz='/p/$x "y"')
    ok(saida_json(out)["updatedInput"]["command"] == 'cd "/p/\\$x \\"y\\"" && ls -la', out)


@caso("em subagente (agent_id): sem saída")
def _(tmp):
    rc, out = roda(HOOK, payload(agent_id="abc"))
    ok(rc == 0 and out == "", f"rc={rc} out={out!r}")


@caso("em subagente (agent_type): sem saída")
def _(tmp):
    rc, out = roda(HOOK, payload(agent_type="dev"))
    ok(rc == 0 and out == "", f"rc={rc} out={out!r}")


@caso("tool diferente de Bash: sem saída")
def _(tmp):
    rc, out = roda(HOOK, payload(tool_name="Read"))
    ok(rc == 0 and out == "", f"rc={rc} out={out!r}")


@caso("CLAUDE_PROJECT_DIR ausente: sem saída")
def _(tmp):
    rc, out = roda(HOOK, payload(), raiz=None)
    ok(rc == 0 and out == "", f"rc={rc} out={out!r}")


@caso("JSON inválido: sai 0 sem saída")
def _(tmp):
    rc, out = roda(HOOK, "{isso não é json")
    ok(rc == 0 and out == "", f"rc={rc} out={out!r}")


@caso("sem cwd ou sem comando no payload: sem saída")
def _(tmp):
    sem_cwd = payload()
    del sem_cwd["cwd"]
    rc, out = roda(HOOK, sem_cwd)
    ok(rc == 0 and out == "", f"sem cwd: rc={rc} out={out!r}")
    rc, out = roda(HOOK, payload(comando=""))
    ok(rc == 0 and out == "", f"sem comando: rc={rc} out={out!r}")


@caso("composição com rtk, cwd fora da raiz: um escritor só, prefixo cd + rtk")
def _(tmp):
    rtk = rtk_falso(tmp)
    rc, out = roda(HOOK, payload(comando="git status"), rtk_bin=rtk)
    saida = saida_json(out)
    ok(saida["updatedInput"]["command"] == f'cd "{RAIZ}" && rtk git status', saida)
    ok("permissionDecision" not in saida, "permissionDecision do rtk deve ser descartado")
    # o rtk-root.sh, rodando sozinho com a cwd fora da raiz, fica calado (não disputa)
    rc, out = roda(RTK_ROOT, payload(comando="git status"), rtk_bin=rtk)
    ok(rc == 0 and out == "", f"rtk-root deveria ceder: rc={rc} out={out!r}")


@caso("composição com rtk, comando fora da allowlist do rtk: só o prefixo cd")
def _(tmp):
    rtk = rtk_falso(tmp)
    rc, out = roda(HOOK, payload(comando="cat arquivo"), rtk_bin=rtk)
    ok(saida_json(out)["updatedInput"]["command"] == f'cd "{RAIZ}" && cat arquivo', out)


@caso("cwd na raiz: rtk-root.sh continua agindo sozinho")
def _(tmp):
    rtk = rtk_falso(tmp)
    rc, out = roda(RTK_ROOT, payload(cwd=RAIZ, comando="git status"), rtk_bin=rtk)
    ok(saida_json(out)["updatedInput"]["command"] == "rtk git status", out)


def main():
    falhas = 0
    for nome, fn in CASOS:
        tmp = tempfile.mkdtemp(prefix="volta-pasta-base-")
        try:
            fn(tmp)
            print(f"ok   - {nome}")
        except Exception as e:
            falhas += 1
            print(f"FAIL - {nome}: {e}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{len(CASOS) - falhas}/{len(CASOS)} casos passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
