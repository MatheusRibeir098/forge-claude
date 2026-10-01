#!/usr/bin/env python3
"""Testes do hook `deny-aws-destrutivo.py` — só stdlib, sem dependência externa.

    python3 plugins/forge/hooks/tests/test_deny_aws.py

Cobre o furo medido (flag global antes do serviço escapa do prefixo literal das permissions),
os encadeamentos (&&, ||, ;, |, $(...), bash -c) e o falso positivo que não pode acontecer
(string que só MENCIONA "aws s3 rm" sem invocar o CLI).
"""
import json
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(os.path.dirname(AQUI), "deny-aws-destrutivo.py")

CASOS = []


def caso(nome):
    def deco(fn):
        CASOS.append((nome, fn))
        return fn
    return deco


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def payload(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def roda(entrada):
    """Executa o hook. Devolve (returncode, stdout, decisao ou None)."""
    bruto = entrada if isinstance(entrada, str) else json.dumps(entrada, ensure_ascii=False)
    p = subprocess.run([sys.executable, HOOK], input=bruto, capture_output=True, text=True)
    decisao = None
    if p.stdout.strip():
        saida = json.loads(p.stdout)["hookSpecificOutput"]
        decisao = saida["permissionDecision"]
        return p.returncode, p.stdout, decisao, saida.get("permissionDecisionReason", "")
    return p.returncode, p.stdout, decisao, ""


def negado(cmd):
    rc, _, decisao, razao = roda(payload(cmd))
    ok(rc == 0, f"exit {rc} para {cmd!r}")
    ok(decisao == "deny", f"deveria negar {cmd!r}, decisão foi {decisao!r}")
    return razao


def liberado(cmd):
    rc, _, decisao, razao = roda(payload(cmd))
    ok(rc == 0, f"exit {rc} para {cmd!r}")
    ok(decisao is None, f"deveria liberar {cmd!r}, mas negou: {razao!r}")


# --------------------------------------------------------------------------- o quadro do furo

@caso("(a) aws s3 rm direto -> negado (já funcionava, tem que continuar)")
def _a():
    negado("aws s3 rm s3://bucket --recursive")


@caso("(b) aws --profile prod s3 rm -> negado (o furo do prefixo literal)")
def _b():
    razao = negado("aws --profile prod s3 rm s3://bucket")
    ok("prod" in razao, f"não citou o profile na razão: {razao!r}")


@caso("(c) aws --region us-east-1 iam delete-role -> negado (o furo do prefixo literal)")
def _c():
    negado("aws --region us-east-1 iam delete-role --role-name x")


@caso("(d) aws s3 ls s3://bucket -> liberado (é leitura)")
def _d():
    liberado("aws s3 ls s3://bucket")


# --------------------------------------------------------------------------- leitura liberada

@caso("(e) leitura básica liberada: s3 ls, sts get-caller-identity, ec2 describe, iam list")
def _e():
    liberado("aws s3 ls")
    liberado("aws sts get-caller-identity")
    liberado("aws ec2 describe-instances")
    liberado("aws iam list-roles")


# --------------------------------------------------------------------------- identidade

@caso("(f) mutação de identidade negada mesmo sem prefixo delete-/remove-")
def _f():
    negado("aws iam attach-role-policy --role-name x --policy-arn y")
    negado("aws iam create-access-key --user-name x")
    negado("aws organizations attach-policy --policy-id x --target-id y")


# --------------------------------------------------------------------------- mutação reversível

@caso("(g) mutação reversível passa (fica com o ask, não é problema deste hook)")
def _g():
    liberado("aws lambda create-function --function-name x")
    liberado("aws dynamodb update-table --table-name x")


# --------------------------------------------------------------------------- encadeamentos

@caso("(h) encadeado com && e --profile antes do serviço -> negado")
def _h():
    razao = negado("cd /tmp && aws --profile prod s3 rm s3://x")
    ok("prod" in razao, f"não citou o profile: {razao!r}")


@caso("(i) encadeado com && mas só leitura -> liberado")
def _i():
    liberado("aws s3 ls && echo ok")


@caso("(j) dentro de $(...) -> negado")
def _j():
    negado("$(aws iam delete-role --role-name x)")


@caso("(j2) outros separadores: ; | || dentro de bash -c")
def _j2():
    negado("aws s3 ls ; aws iam delete-role --role-name x")
    negado("foo | aws s3 rm s3://y")
    negado("aws s3 ls || aws organizations close-account")
    negado('bash -c "aws iam delete-role --role-name w"')


# --------------------------------------------------------------------------- falso positivo

@caso("(k) só menciona a string 'aws s3 rm' -> liberado (não é invocação do CLI)")
def _k():
    liberado('grep -rn "aws s3 rm" .')
    liberado('echo "aws iam delete-role"')


# --------------------------------------------------------------------------- payload ilegível

@caso("(l) payload ilegível e comando vazio -> silêncio, exit 0")
def _l():
    rc, out, decisao, _ = roda("isso não é json")
    ok(rc == 0, f"exit {rc} para JSON quebrado")
    ok(decisao is None, "não deveria ter decisão nenhuma para JSON quebrado")

    rc, out, decisao, _ = roda(payload(""))
    ok(rc == 0, f"exit {rc} para comando vazio")
    ok(decisao is None, "comando vazio não deveria gerar decisão")

    rc, out, decisao, _ = roda({"tool_name": "Bash"})  # sem tool_input
    ok(rc == 0, f"exit {rc} sem tool_input")
    ok(decisao is None, "sem tool_input não deveria gerar decisão")

    rc, out, decisao, _ = roda(payload("aws s3 rm --profile 'x"))  # aspas malformadas
    ok(rc == 0, f"exit {rc} para aspas malformadas")


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
