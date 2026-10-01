#!/usr/bin/env python3
"""Testes do hook `delega-varredura.py` — só stdlib, sem dependência externa.

    python3 plugins/forge/hooks/tests/test_delega_varredura.py

Cada caso isola o estado do contador apontando `TMPDIR` para um diretório temporário próprio
(e limpando `FORGE_STATE_DIR`/`XDG_RUNTIME_DIR` do ambiente herdado), para exercitar o mesmo
caminho de derivação padrão do hook (`forge/leituras/<session_id>`) e não vazar contagem
entre casos que não deveriam se enxergar.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(os.path.dirname(AQUI), "delega-varredura.py")

CASOS = []


def caso(nome):
    def deco(fn):
        CASOS.append((nome, fn))
        return fn
    return deco


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def payload(tool_name=None, session_id="sessao-teste", agent_id=None, **extra):
    d = {}
    if tool_name is not None:
        d["tool_name"] = tool_name
    if session_id is not None:
        d["session_id"] = session_id
    if agent_id is not None:
        d["agent_id"] = agent_id
    d.update(extra)
    return d


def roda(entrada, tmp_base, limiar=None, limiar_aws=None):
    """Executa o hook com TMPDIR apontando para `tmp_base` (isola o contador). Devolve
    (returncode, stdout, additionalContext ou None)."""
    env = dict(os.environ)
    env.pop("FORGE_STATE_DIR", None)
    env.pop("XDG_RUNTIME_DIR", None)
    env["TMPDIR"] = tmp_base
    if limiar is not None:
        env["FORGE_LEITURA_LIMIAR"] = str(limiar)
    else:
        env.pop("FORGE_LEITURA_LIMIAR", None)
    if limiar_aws is not None:
        env["FORGE_AWS_LIMIAR"] = str(limiar_aws)
    else:
        env.pop("FORGE_AWS_LIMIAR", None)

    bruto = entrada if isinstance(entrada, str) else json.dumps(entrada, ensure_ascii=False)
    p = subprocess.run([sys.executable, HOOK], input=bruto, capture_output=True, text=True,
                        env=env)
    ctx = None
    if p.stdout.strip():
        saida = json.loads(p.stdout)
        ok("permissionDecision" not in saida.get("hookSpecificOutput", {}),
           "este hook NUNCA deveria emitir permissionDecision")
        ctx = saida["hookSpecificOutput"]["additionalContext"]
    return p.returncode, p.stdout, ctx


class Sandbox:
    """Um TMPDIR descartável por caso de teste."""

    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix="forge-leituras-test-")
        return self.dir

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)


def ler(tmp_base, tool_name="Read", session_id="sessao-teste", limiar=None):
    return roda(payload(tool_name=tool_name, session_id=session_id), tmp_base, limiar=limiar)


def bash(tmp_base, command, session_id="sessao-teste", limiar=None, limiar_aws=None,
         agent_id=None):
    """Executa o hook simulando uma chamada `Bash` com o `command` dado."""
    return roda(
        payload(tool_name="Bash", session_id=session_id, agent_id=agent_id,
                tool_input={"command": command}),
        tmp_base, limiar=limiar, limiar_aws=limiar_aws,
    )


# --------------------------------------------------------------------------- casos

@caso("(a) 7 leituras seguidas não injeta; a 8ª injeta")
def _a():
    with Sandbox() as tmp:
        for i in range(1, 8):
            rc, out, ctx = ler(tmp)
            ok(rc == 0, f"exit {rc} na leitura {i}")
            ok(ctx is None, f"leitura {i}/7 não deveria injetar nada: {ctx!r}")
        rc, out, ctx = ler(tmp)
        ok(rc == 0, f"exit {rc} na 8ª leitura")
        ok(ctx is not None, "a 8ª leitura consecutiva deveria injetar o lembrete")
        ok("8" in ctx, f"lembrete deveria citar a contagem: {ctx!r}")
        ok("scout" in ctx, f"lembrete deveria recomendar o scout: {ctx!r}")
        ok("US$ 0,08" in ctx, f"lembrete deveria citar o custo do scout: {ctx!r}")


@caso("(b) Edit no meio da corrida zera: 5 leituras + Edit + 5 leituras -> não injeta")
def _b():
    with Sandbox() as tmp:
        for _ in range(5):
            _, _, ctx = ler(tmp)
            ok(ctx is None, "não deveria injetar nas 5 primeiras leituras")
        _, _, ctx = roda(payload(tool_name="Edit"), tmp)
        ok(ctx is None, "Edit não injeta nada, só zera")
        for i in range(5):
            _, _, ctx = ler(tmp)
            ok(ctx is None, f"leitura {i + 1}/5 pós-Edit não deveria injetar: {ctx!r}")


@caso("(c) Agent no meio da corrida zera (delegar é o comportamento desejado)")
def _c():
    with Sandbox() as tmp:
        for _ in range(5):
            _, _, ctx = ler(tmp)
            ok(ctx is None, "não deveria injetar nas 5 primeiras leituras")
        _, _, ctx = roda(payload(tool_name="Agent"), tmp)
        ok(ctx is None, "Agent não injeta nada, só zera")
        for i in range(5):
            _, _, ctx = ler(tmp)
            ok(ctx is None, f"leitura {i + 1}/5 pós-Agent não deveria injetar: {ctx!r}")


@caso("(d) payload com agent_id (subagente) -> silêncio, mesmo com 20 leituras")
def _d():
    with Sandbox() as tmp:
        for i in range(20):
            rc, out, ctx = roda(
                payload(tool_name="Read", session_id="sub", agent_id="a1b2c3"), tmp)
            ok(rc == 0, f"exit {rc} na leitura {i} do subagente")
            ok(out.strip() == "", f"subagente não deveria gerar lembrete: {out!r}")


@caso("(e) depois de injetar, o contador zera: 8 leituras voltam a injetar, as do meio não")
def _e():
    with Sandbox() as tmp:
        for _ in range(7):
            _, _, ctx = ler(tmp)
            ok(ctx is None, "não deveria injetar antes da 8ª")
        _, _, ctx = ler(tmp)
        ok(ctx is not None, "a 8ª deveria injetar (primeira corrida)")

        # cooldown: precisa de outra corrida INTEIRA de 8 para disparar de novo
        for i in range(7):
            _, _, ctx = ler(tmp)
            ok(ctx is None, f"leitura {i + 1}/7 pós-cooldown não deveria injetar: {ctx!r}")
        _, _, ctx = ler(tmp)
        ok(ctx is not None, "a 8ª leitura da segunda corrida deveria injetar de novo")


@caso("(f) FORGE_LEITURA_LIMIAR=3 altera o comportamento")
def _f():
    with Sandbox() as tmp:
        for _ in range(2):
            _, _, ctx = ler(tmp, limiar=3)
            ok(ctx is None, "não deveria injetar antes do limiar customizado")
        _, _, ctx = ler(tmp, limiar=3)
        ok(ctx is not None, "deveria injetar na 3ª leitura com FORGE_LEITURA_LIMIAR=3")
        ok("3" in ctx, f"lembrete deveria citar o limiar customizado: {ctx!r}")


@caso("(g) sessões diferentes contam separado e não interferem")
def _g():
    with Sandbox() as tmp:
        for _ in range(7):
            _, _, ctx = ler(tmp, session_id="sessao-a")
            ok(ctx is None, "sessao-a não deveria injetar antes da 8ª")
        for _ in range(7):
            _, _, ctx = ler(tmp, session_id="sessao-b")
            ok(ctx is None, "sessao-b não deveria injetar antes da 8ª (contador próprio)")
        _, _, ctx_a = ler(tmp, session_id="sessao-a")
        ok(ctx_a is not None, "8ª leitura da sessao-a deveria injetar")
        _, _, ctx_b = ler(tmp, session_id="sessao-b")
        ok(ctx_b is not None, "8ª leitura da sessao-b deveria injetar (independente da a)")


@caso("(h) payload ilegível / sem tool_name -> silêncio, exit 0")
def _h():
    with Sandbox() as tmp:
        for bruto in ("isto não é json", "", "[1,2,3]", "null", '{"tool_input": 42}'):
            rc, out, _ = roda(bruto, tmp)
            ok(rc == 0, f"exit {rc} para {bruto!r}")
            ok(out.strip() == "", f"payload ilegível não deveria gerar saída: {out!r}")

        rc, out, _ = roda(payload(session_id="sem-tool"), tmp)  # sem tool_name
        ok(rc == 0, f"exit {rc} sem tool_name")
        ok(out.strip() == "", f"sem tool_name não deveria gerar saída: {out!r}")

        rc, out, _ = roda({"tool_name": "", "session_id": "vazio"}, tmp)  # tool_name vazio
        ok(rc == 0, f"exit {rc} com tool_name vazio")
        ok(out.strip() == "", f"tool_name vazio não deveria gerar saída: {out!r}")


@caso("(i) 3 comandos `aws` seguidos disparam a mensagem AWS-específica")
def _i():
    with Sandbox() as tmp:
        _, _, ctx1 = bash(tmp, "aws stepfunctions get-execution-history --execution-arn x")
        ok(ctx1 is None, "1º comando aws não deveria disparar ainda")
        _, _, ctx2 = bash(tmp, "aws logs filter-log-events --log-group-name x")
        ok(ctx2 is None, "2º comando aws não deveria disparar ainda")
        _, _, ctx3 = bash(tmp, "aws states describe-execution --execution-arn x")
        ok(ctx3 is not None, "3º comando aws deveria disparar a mensagem AWS")
        ok("scout" in ctx3, f"mensagem AWS deveria citar o scout: {ctx3!r}")
        ok("investigacao-incidente-aws" in ctx3,
           f"mensagem AWS deveria citar a skill: {ctx3!r}")


@caso("(j) 2 comandos `aws` seguidos ainda não disparam (abaixo do limiar)")
def _j():
    with Sandbox() as tmp:
        _, _, ctx1 = bash(tmp, "aws stepfunctions get-execution-history --execution-arn x")
        ok(ctx1 is None, "1º comando aws não deveria disparar")
        _, _, ctx2 = bash(tmp, "aws logs filter-log-events --log-group-name x")
        ok(ctx2 is None, "2º comando aws não deveria disparar")


@caso("(k) Bash não-aws no meio da sequência aws não reseta o contador aws")
def _k():
    with Sandbox() as tmp:
        _, _, ctx1 = bash(tmp, "aws stepfunctions get-execution-history --execution-arn x")
        ok(ctx1 is None, "1ª aws não deveria disparar")
        _, _, ctx2 = bash(tmp, "aws logs filter-log-events --log-group-name x")
        ok(ctx2 is None, "2ª aws não deveria disparar")
        _, _, ctx3 = bash(tmp, "git status")
        ok(ctx3 is None, "Bash não-aws no meio não deveria disparar nada")
        _, _, ctx4 = bash(tmp, "aws states describe-execution --execution-arn x")
        ok(ctx4 is not None,
           "3ª aws (4ª chamada Bash no total) deveria disparar — git status não zera o aws")


@caso("(l) Bash aws incrementa os dois contadores; 8 leituras intercaladas com aws "
      "disparam o limiar geral sem nunca bater 3 aws seguidos")
def _l():
    with Sandbox() as tmp:
        # só 2 chamadas aws no total (o contador aws NÃO zera com Read no meio, então mais
        # de 2 aws intercaladas com Read bateria o limiar aws de 3 antes do geral de 8).
        chamadas = [
            lambda: bash(tmp, "aws stepfunctions get-execution-history --execution-arn x"),
            lambda: ler(tmp),
            lambda: bash(tmp, "aws logs filter-log-events --log-group-name x"),
            lambda: ler(tmp),
            lambda: ler(tmp),
            lambda: ler(tmp),
            lambda: ler(tmp),
        ]
        for i, chamada in enumerate(chamadas):
            _, _, ctx = chamada()
            ok(ctx is None, f"chamada {i + 1}/7 não deveria disparar nada ainda: {ctx!r}")
        # 8ª chamada de leitura: limiar geral (8) bate, aws ficou em 2 (nunca bateu 3)
        _, _, ctx8 = ler(tmp)
        ok(ctx8 is not None, "8ª chamada deveria disparar o limiar geral")
        ok("scout" in ctx8, f"mensagem geral deveria citar o scout: {ctx8!r}")
        ok("investigacao-incidente-aws" not in ctx8,
           f"limiar geral não deveria usar a mensagem AWS-específica: {ctx8!r}")


@caso("(m) FORGE_AWS_LIMIAR muda o comportamento")
def _m():
    with Sandbox() as tmp:
        _, _, ctx1 = bash(tmp, "aws stepfunctions get-execution-history --execution-arn x",
                           limiar_aws=2)
        ok(ctx1 is None, "1º comando aws não deveria disparar ainda com FORGE_AWS_LIMIAR=2")
        _, _, ctx2 = bash(tmp, "aws logs filter-log-events --log-group-name x", limiar_aws=2)
        ok(ctx2 is not None, "2º comando aws deveria disparar com FORGE_AWS_LIMIAR=2")
        ok("2" in ctx2, f"mensagem AWS deveria citar o limiar customizado: {ctx2!r}")


@caso("(n) payload com agent_id (subagente) fica em silêncio mesmo com várias aws seguidas")
def _n():
    with Sandbox() as tmp:
        for i in range(5):
            rc, out, ctx = bash(tmp, "aws stepfunctions get-execution-history --execution-arn x",
                                 session_id="sub", agent_id="a1b2c3")
            ok(rc == 0, f"exit {rc} na chamada aws {i} do subagente")
            ok(out.strip() == "", f"subagente não deveria gerar lembrete: {out!r}")


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
