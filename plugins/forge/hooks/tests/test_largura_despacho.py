#!/usr/bin/env python3
"""Testes do hook `largura-despacho.py` — só stdlib, sem dependência externa.

    python3 plugins/forge/hooks/tests/test_largura_despacho.py

Os payloads e transcripts vêm de `fixtures/` (formato do transcript JSONL da CLI: uma linha
`type: assistant` por bloco, todas com o mesmo `message.id` quando são da mesma mensagem). Cada
caso roda numa pasta de estado própria (`FORGE_STATE_DIR`) para não vazar dedup nem flag.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(os.path.dirname(AQUI), "largura-despacho.py")
FIXTURES = os.path.join(AQUI, "fixtures")

CASOS = []


def caso(nome):
    def deco(fn):
        CASOS.append((nome, fn))
        return fn
    return deco


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


def fixture_json(nome):
    with open(os.path.join(FIXTURES, nome), encoding="utf-8") as fh:
        return json.load(fh)


class Sandbox:
    """Pasta de estado e cópia dos transcripts, descartáveis por caso."""

    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix="forge-largura-test-")
        self.estado = os.path.join(self.dir, "estado")
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)

    def transcript(self, nome, troca=None):
        """Cópia da fixture, com `troca` = (de, para) aplicado ao texto."""
        with open(os.path.join(FIXTURES, nome), encoding="utf-8") as fh:
            texto = fh.read()
        if troca:
            texto = texto.replace(*troca)
        destino = os.path.join(self.dir, nome)
        with open(destino, "w", encoding="utf-8") as fh:
            fh.write(texto)
        return destino


def roda(entrada, estado, extra_env=None):
    """Executa o hook. Devolve (returncode, stdout, saida JSON ou None)."""
    env = dict(os.environ)
    env.pop("XDG_RUNTIME_DIR", None)
    env["FORGE_STATE_DIR"] = estado
    env.update(extra_env or {})
    bruto = entrada if isinstance(entrada, str) else json.dumps(entrada, ensure_ascii=False)
    p = subprocess.run([sys.executable, HOOK], input=bruto, capture_output=True, text=True,
                       env=env)
    saida = json.loads(p.stdout) if p.stdout.strip() else None
    if saida is not None:
        especifico = saida.get("hookSpecificOutput", {})
        ok(set(saida) == {"hookSpecificOutput"}, f"só hookSpecificOutput era esperado: {saida!r}")
        for proibido in ("permissionDecision", "updatedInput", "decision"):
            ok(proibido not in especifico and proibido not in saida,
               f"o hook nunca deve emitir {proibido}: {saida!r}")
    return p.returncode, p.stdout, saida


def payload_agent(transcript, tool_use_id="toolu_01AAA", subagent_type=None, agent_id=None):
    d = fixture_json("posttooluse-agent-largura.json")
    d["transcript_path"] = transcript
    if tool_use_id is None:
        d.pop("tool_use_id")
    else:
        d["tool_use_id"] = tool_use_id
    if subagent_type:
        d["tool_input"]["subagent_type"] = subagent_type
    if agent_id:
        d["agent_id"] = agent_id
    return d


def payload_prompt(texto, session_id=None):
    d = fixture_json("userpromptsubmit.json")
    d["prompt"] = texto
    if session_id:
        d["session_id"] = session_id
    return d


def contexto(saida, evento):
    ok(saida is not None, "esperava additionalContext e o hook ficou calado")
    especifico = saida["hookSpecificOutput"]
    ok(especifico["hookEventName"] == evento, f"hookEventName errado: {especifico!r}")
    return especifico["additionalContext"]


def flag(sb):
    return os.path.join(sb.estado, "pediu_agentes")


# --------------------------------------------------------------------------- PostToolUse(Agent)

@caso("1 Agent sozinho (forge:scout) -> cutuca com o texto, teto 12 e PostToolUse")
def _um_agente():
    with Sandbox() as sb:
        t = sb.transcript("transcript-despacho-1-agent.jsonl")
        rc, _, saida = roda(payload_agent(t), sb.estado)
        ok(rc == 0, f"exit {rc}")
        texto = contexto(saida, "PostToolUse")
        ok("Saiu 1 agente sozinho" in texto and "teto 12" in texto, f"texto: {texto!r}")


@caso("3 Agents na mesma mensagem -> silêncio")
def _tres_agentes():
    with Sandbox() as sb:
        t = sb.transcript("transcript-despacho-3-agents.jsonl")
        for tool_use_id in ("toolu_01BBB", "toolu_02BBB", "toolu_03BBB", None):
            rc, out, _ = roda(payload_agent(t, tool_use_id=tool_use_id), sb.estado)
            ok(rc == 0 and out.strip() == "", f"lote de 3 não cutuca ({tool_use_id}): {out!r}")


@caso("payload de subagente (agent_id) -> silêncio")
def _subagente():
    with Sandbox() as sb:
        t = sb.transcript("transcript-despacho-1-agent.jsonl")
        rc, out, _ = roda(payload_agent(t, agent_id="a1b2c3"), sb.estado)
        ok(rc == 0 and out.strip() == "", f"subagente não deveria gerar saída: {out!r}")


@caso("dedup: o mesmo message.id cutuca uma vez só")
def _dedup():
    with Sandbox() as sb:
        t = sb.transcript("transcript-despacho-1-agent.jsonl")
        _, _, primeira = roda(payload_agent(t), sb.estado)
        contexto(primeira, "PostToolUse")
        for _ in range(2):
            rc, out, _ = roda(payload_agent(t), sb.estado)
            ok(rc == 0 and out.strip() == "", f"repetição não deveria cutucar: {out!r}")


@caso("dedup é por message.id: outra mensagem com 1 Agent cutuca de novo")
def _dedup_outra_mensagem():
    with Sandbox() as sb:
        a = sb.transcript("transcript-despacho-1-agent.jsonl")
        _, _, saida = roda(payload_agent(a), sb.estado)
        contexto(saida, "PostToolUse")
        b = sb.transcript("transcript-despacho-1-agent.jsonl", ("msg_01UMAGENTE", "msg_02OUTRA"))
        _, _, saida = roda(payload_agent(b), sb.estado)
        contexto(saida, "PostToolUse")


@caso("tipo fora da lista (outro-plugin:revisor) -> silêncio")
def _tipo_fora():
    with Sandbox() as sb:
        t = sb.transcript("transcript-despacho-tipo-fora.jsonl")
        rc, out, _ = roda(payload_agent(t, tool_use_id="toolu_01CCC"), sb.estado)
        ok(rc == 0 and out.strip() == "", f"tipo fora da lista não cutuca: {out!r}")


@caso("general-purpose e Explore sozinhos também cutucam")
def _tipos_genericos():
    for tipo in ("general-purpose", "Explore", "forge:dev", "forge:tester"):
        with Sandbox() as sb:
            t = sb.transcript("transcript-despacho-1-agent.jsonl", ("forge:scout", tipo))
            _, _, saida = roda(payload_agent(t), sb.estado)
            contexto(saida, "PostToolUse")


@caso("sem tool_use_id no payload usa a última mensagem do assistente")
def _sem_tool_use_id():
    with Sandbox() as sb:
        t = sb.transcript("transcript-despacho-1-agent.jsonl")
        _, _, saida = roda(payload_agent(t, tool_use_id=None), sb.estado)
        contexto(saida, "PostToolUse")


@caso("transcript ausente, vazio ou ilegível e stdin ruim -> exit 0 calado")
def _ilegivel():
    with Sandbox() as sb:
        vazio = os.path.join(sb.dir, "vazio.jsonl")
        open(vazio, "w").close()
        lixo = os.path.join(sb.dir, "lixo.jsonl")
        with open(lixo, "w", encoding="utf-8") as fh:
            fh.write("isto não é json\n{\n")
        entradas = [payload_agent(os.path.join(sb.dir, "nao-existe.jsonl")),
                    payload_agent(vazio), payload_agent(lixo),
                    {"hook_event_name": "PostToolUse", "tool_name": "Agent"},
                    "isto não é json", "", "[1,2]", "null",
                    {"hook_event_name": "Stop"}]
        for entrada in entradas:
            rc, out, _ = roda(entrada, sb.estado)
            ok(rc == 0 and out.strip() == "", f"deveria calar: {entrada!r} -> {out!r}")


@caso("diretório de estado inacessível não derruba o hook")
def _estado_inacessivel():
    with Sandbox() as sb:
        t = sb.transcript("transcript-despacho-1-agent.jsonl")
        arquivo = os.path.join(sb.dir, "arquivo")
        open(arquivo, "w").close()
        rc, _, _ = roda(payload_agent(t), os.path.join(arquivo, "dentro"))
        ok(rc == 0, f"exit {rc}")


# --------------------------------------------------------------------------- UserPromptSubmit

@caso("prompt pedindo agentes -> contexto UserPromptSubmit e flag gravada")
def _prompt_com_pedido():
    with Sandbox() as sb:
        rc, _, saida = roda(payload_prompt("Analise o projeto com scouts em paralelo"), sb.estado)
        ok(rc == 0, f"exit {rc}")
        texto = contexto(saida, "UserPromptSubmit")
        ok("pediu agentes" in texto and "3 ou mais scouts" in texto, f"texto: {texto!r}")
        ok(os.path.isfile(flag(sb)), "a flag pediu_agentes deveria existir")


@caso("prompt sem pedido -> silêncio e a flag anterior é apagada")
def _prompt_sem_pedido():
    with Sandbox() as sb:
        roda(payload_prompt("invoque os agentes"), sb.estado)
        ok(os.path.isfile(flag(sb)), "pré-condição: flag gravada")
        rc, out, _ = roda(payload_prompt("corrija o bug do login"), sb.estado)
        ok(rc == 0 and out.strip() == "", f"sem pedido não deveria gerar saída: {out!r}")
        ok(not os.path.exists(flag(sb)), "a flag deveria ter sido apagada")


@caso("regex do pedido: scout, invoca/invoke, subagente, agentes, paralelo (sem caixa)")
def _prompt_regex():
    com = ["use um SCOUT", "Invoca o dev", "invoque o tester", "invoke tudo", "chame subagentes", "sub-agente aí",
           "mande os agentes", "rode em Paralelo", "trabalho paralelizado"]
    sem = ["corrija o login", "o agente anterior falhou", "escoutar não conta",
           "calcule a geometria do cubo", ""]
    for texto in com:
        with Sandbox() as sb:
            _, _, saida = roda(payload_prompt(texto), sb.estado)
            contexto(saida, "UserPromptSubmit")
    for texto in sem:
        with Sandbox() as sb:
            rc, out, _ = roda(payload_prompt(texto), sb.estado)
            ok(rc == 0 and out.strip() == "", f"{texto!r} não pede agentes: {out!r}")


@caso("prompt de subagente (agent_id) e prompt não-string -> silêncio")
def _prompt_ignorado():
    with Sandbox() as sb:
        d = payload_prompt("use scouts")
        d["agent_id"] = "a1b2c3"
        rc, out, _ = roda(d, sb.estado)
        ok(rc == 0 and out.strip() == "", f"subagente não deveria gerar saída: {out!r}")
        ok(not os.path.exists(flag(sb)), "subagente não grava flag")
        d = payload_prompt("x")
        d["prompt"] = 42
        rc, out, _ = roda(d, sb.estado)
        ok(rc == 0 and out.strip() == "", f"prompt não-string deveria calar: {out!r}")


@caso("sem FORGE_STATE_DIR a flag cai em forge/leituras/<session_id> (a pasta do delega-varredura)")
def _flag_no_caminho_do_delega():
    with Sandbox() as sb:
        env = dict(os.environ)
        env.pop("FORGE_STATE_DIR", None)
        env.pop("XDG_RUNTIME_DIR", None)
        env["TMPDIR"] = sb.dir
        d = payload_prompt("use scouts", session_id="sessao-teste")
        p = subprocess.run([sys.executable, HOOK], input=json.dumps(d), capture_output=True,
                           text=True, env=env)
        ok(p.returncode == 0, f"exit {p.returncode}")
        esperado = os.path.join(sb.dir, "forge", "leituras", "sessao-teste", "pediu_agentes")
        ok(os.path.isfile(esperado), f"flag deveria estar em {esperado}")


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
