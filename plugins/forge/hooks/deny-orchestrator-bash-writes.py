#!/usr/bin/env python3
"""PreToolUse (Bash, SÓ sessão principal): barra escrita de código de produto feita por Bash.

POR QUE EXISTE: o `deny-orchestrator-code-edits.sh` barra Write|Edit do orquestrador, mas sem
este hook, depois de uma negação, o orquestrador poderia gravar o MESMO conteúdo por
`cat > x <<EOF`, `tee` ou `sed -i` — furando o Invariante 1 por um caminho que aquele hook não vê.

MESMO CRITÉRIO DE SESSÃO do hook de Write|Edit: payload com `agent_type` => subagente
(dev/tester), que escreve livremente => este hook fica calado. Sem `agent_type` => orquestrador.

MESMA REGRA DE CAMINHO: a decisão vem de `lib/decisao_escrita.avalia_caminho` (a mesma função
do hook de Write|Edit), com a raiz do projeto tirada do payload do mesmo jeito. Caminho
relativo é resolvido contra o cwd efetivo (o do payload, ajustado por `cd x &&` anteriores);
caminho fora da raiz segue o tratamento do hook de Write|Edit (livre: scratchpad, /tmp). A
única exceção própria daqui são os nós `/dev/*` (`> /dev/null`).

O QUE É DETECTADO (alvo de escrita, comando a comando, separados por `&&`, `||`, `;`, `|`):
  - redirecionamento `>`, `>>`, `&>` para um caminho (inclui `cat > x <<EOF`);
  - `tee` / `tee -a`;
  - `sed -i` / `perl -i`;
  - o destino de `cp`, `mv` e `install` (destino-diretório vira `<dir>/<basename da origem>`).
O QUE NUNCA É BARRADO: `2>&1`, `>&2`, `> /dev/null`, strings entre aspas que só mencionam
esses comandos (`grep "cat > x"`), alvos com `$VAR`/`$(...)`/glob (não dá para resolver) e
tudo que o hook de Write|Edit liberaria.

LIMITAÇÃO CONHECIDA: escrita feita por interpretador, como `python -c 'open("x.py","w")...'`,
`node -e`, `ruby -e` etc., NÃO é detectada — o conteúdo do script não é analisado. É um freio
contra o atalho comum (`cat >`, `tee`, `sed -i`), não uma sandbox.

NUNCA QUEBRA A CHAMADA: comando ilegível (aspas desbalanceadas) ou qualquer exceção => exit 0
sem saída. Só emite `permissionDecision: deny`; nunca `updatedInput` (hooks PreToolUse do mesmo
evento rodam em paralelo, e só um escritor de `updatedInput` pode existir).
"""
import json
import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from decisao_escrita import avalia_caminho, raiz_do_payload  # noqa: E402
from shell_tokens import (  # noqa: E402
    eh_redirecao, novo_cwd_do_cd, resolve, segmentos, sem_prefixos, tokeniza,
)

_SO_DIGITOS = re.compile(r"^\d+$")
_OPCOES_COM_VALOR_CP = {"-t", "--target-directory", "-S", "--suffix", "-m", "--mode",
                        "-o", "--owner", "-g", "--group"}
_DINAMICO = re.compile(r"[$`*?\[]")


def _separa_redirecoes(segmento):
    """Devolve (argumentos sem redirecionamentos, alvos de redirecionamento de saída)."""
    args, alvos, i = [], [], 0
    while i < len(segmento):
        tok = segmento[i]
        if not eh_redirecao(tok):
            args.append(tok)
            i += 1
            continue
        if args and _SO_DIGITOS.match(args[-1]):
            args.pop()  # o descritor de `2>file`
        proximo = segmento[i + 1] if i + 1 < len(segmento) else None
        i += 2
        if proximo is None or ("<" in tok and ">" not in tok):
            continue  # entrada/heredoc: o próximo token é a fonte/delimitador
        if tok.endswith("&") and (_SO_DIGITOS.match(proximo) or proximo == "-"):
            continue  # duplicação de descritor: 2>&1, >&2
        alvos.append(proximo)
    return args, alvos


def _separa_opcoes(args, com_valor):
    """Devolve (posicionais, valores das opções em `com_valor`)."""
    posicionais, valores, i = [], {}, 0
    while i < len(args):
        a = args[i]
        if a in com_valor and i + 1 < len(args):
            valores[a] = args[i + 1]
            i += 2
        elif a.startswith("--") and "=" in a and a.split("=", 1)[0] in com_valor:
            valores[a.split("=", 1)[0]] = a.split("=", 1)[1]
            i += 1
        elif a.startswith("-") and len(a) > 1:
            i += 1
        else:
            posicionais.append(a)
            i += 1
    return posicionais, valores


def _alvos_tee(args):
    return [a for a in args if not a.startswith("-") or a == "-"]


def _alvos_sed_perl(nome, args):
    """Arquivos editados por `sed -i` / `perl -i`; vazio se não for edição in-place."""
    inplace, script_dado, posicionais, i = False, False, [], 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            inplace = inplace or a.startswith("--in-place")
            script_dado = script_dado or a.startswith(("--expression", "--file"))
            i += 2 if a in ("--expression", "--file") else 1
        elif a.startswith("-") and len(a) > 1:
            cluster = a[1:]
            if "i" in cluster:
                inplace = True
            elif cluster[-1] in "eEf" and (nome == "perl" or cluster[-1] in "ef"):
                script_dado = True
                i += 1  # o valor da opção -e/-f é o próximo argumento
            i += 1
        else:
            posicionais.append(a)
            i += 1
    if not inplace:
        return []
    return posicionais if script_dado else posicionais[1:]


def _alvos_cp_mv_install(nome, args, cwd):
    if nome == "install" and any(a in ("-d", "--directory") for a in args):
        return []
    posicionais, valores = _separa_opcoes(args, _OPCOES_COM_VALOR_CP)
    destino_dir = valores.get("-t") or valores.get("--target-directory")
    if destino_dir is not None:
        fontes, destino = posicionais, destino_dir
    elif len(posicionais) >= 2:
        fontes, destino = posicionais[:-1], posicionais[-1]
    else:
        return []
    if destino.endswith("/") or os.path.isdir(resolve(destino, cwd)) or destino_dir is not None:
        return [os.path.join(destino, os.path.basename(f.rstrip("/"))) for f in fontes]
    return [destino]


def alvos_de_escrita(segmento, cwd):
    args, alvos = _separa_redirecoes(segmento)
    _, resto = sem_prefixos(args)
    if not resto:
        return alvos
    nome, argumentos = os.path.basename(resto[0]), resto[1:]
    if nome == "tee":
        alvos += _alvos_tee(argumentos)
    elif nome in ("sed", "perl"):
        alvos += _alvos_sed_perl(nome, argumentos)
    elif nome in ("cp", "mv", "install"):
        alvos += _alvos_cp_mv_install(nome, argumentos, cwd)
    return alvos


def _eh_no_de_dispositivo(caminho):
    return caminho.startswith("/dev/")


def primeiro_alvo_barrado(comando, root, cwd):
    """(caminho absoluto, modo, permitido_desc) do primeiro alvo barrado, ou None."""
    for segmento in segmentos(tokeniza(comando)):
        _, resto = sem_prefixos(segmento)
        if resto and os.path.basename(resto[0]) == "cd":
            cwd = novo_cwd_do_cd(resto[1:], cwd)
            continue
        for alvo in alvos_de_escrita(segmento, cwd):
            if not alvo or _DINAMICO.search(alvo) or _eh_no_de_dispositivo(alvo):
                continue
            absoluto = resolve(alvo, cwd)
            liberado, modo, permitido = avalia_caminho(absoluto, root)
            if not liberado:
                return absoluto, modo, permitido
    return None


def _mensagem(alvo, modo, permitido):
    return (
        f"Escrita de código pelo orquestrador é proibida também via Bash (redirecionamento, tee, "
        f"sed -i, cp/mv/install): alvo barrado {alvo}. Modo detectado: {modo}. Permitido neste "
        f"modo: {permitido}. Delegue ao subagente dev: monte um briefing e invoque-o via "
        "ferramenta Agent. Contornar uma negação anterior do Write/Edit por outra ferramenta "
        "(Bash, tee, sed, python) é proibido."
    )


def main():
    try:
        payload = json.loads(sys.stdin.read())
        if payload.get("agent_type"):
            return  # subagente (dev/tester): escreve livremente
        comando = (payload.get("tool_input") or {}).get("command")
        if not isinstance(comando, str) or not comando.strip():
            return
        root = raiz_do_payload(payload)
        achado = primeiro_alvo_barrado(comando, root, root)
    except Exception:
        return  # hook que explode é pior que hook ausente
    if achado is None:
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": _mensagem(*achado),
    }}))


if __name__ == "__main__":
    main()
