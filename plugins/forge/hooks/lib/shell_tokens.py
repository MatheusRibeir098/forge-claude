"""Leitura de comandos de shell para os hooks de Bash (sem executar nada).

Tokeniza com `shlex.shlex(cmd, posix=True, punctuation_chars=True)`: aspas são removidas e os
operadores (`>`, `>>`, `&>`, `&&`, `|`, `;`, `(`...) viram tokens próprios. Strings entre aspas
que só mencionam comandos (`grep "cat > x"`) continuam sendo UM token com espaços — nunca
viram operador.

Dois cuidados antes de tokenizar:
  - corpos de heredoc são descartados (podem ter aspas desbalanceadas e não são comando);
  - aspas contendo SÓ pontuação (`">"`, `'|'`) viram um marcador, porque depois de removidas as
    aspas elas seriam indistinguíveis do operador.

Comando ilegível => `tokeniza` levanta ValueError; quem chama deve ficar em silêncio.
"""
import os
import re
import shlex

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
_ASPAS_SO_PONTUACAO = re.compile(r"""(["'])[;&|<>()]+\1""")
_ATRIBUICAO = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PREFIXOS = {"sudo", "command", "builtin", "exec", "time", "nohup", "nice", "env"}
_PONTUACAO = set(";&|<>()")


def _normaliza(cmd):
    cmd = cmd.replace("\\\n", " ")
    saida, delimitador = [], None
    for linha in cmd.split("\n"):
        if delimitador is not None:
            if linha.strip() == delimitador:
                delimitador = None
            continue
        saida.append(linha)
        achou = _HEREDOC.search(linha)
        if achou:
            delimitador = achou.group(2)
    return _ASPAS_SO_PONTUACAO.sub("__ASPAS__", " ; ".join(saida))


def tokeniza(cmd):
    lex = shlex.shlex(_normaliza(cmd), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    return list(lex)


def so_pontuacao(token):
    return bool(token) and all(c in _PONTUACAO for c in token)


def eh_redirecao(token):
    return so_pontuacao(token) and ("<" in token or ">" in token)


def segmentos(tokens):
    """Quebra a lista de tokens em comandos simples (`&&`, `||`, `;`, `|`, `(`, `)`, `&`)."""
    atual, todos = [], []
    for tok in tokens:
        if so_pontuacao(tok) and not eh_redirecao(tok):
            if atual:
                todos.append(atual)
            atual = []
        else:
            atual.append(tok)
    if atual:
        todos.append(atual)
    return todos


def sem_prefixos(segmento):
    """Remove `VAR=x` iniciais e wrappers (sudo, command, env...). Devolve (atribuicoes, resto)."""
    i, atribuicoes = 0, []
    while i < len(segmento):
        if _ATRIBUICAO.match(segmento[i]):
            atribuicoes.append(segmento[i])
        elif segmento[i] not in _PREFIXOS:
            break
        i += 1
    return atribuicoes, segmento[i:]


def resolve(caminho, cwd):
    caminho = os.path.expanduser(caminho)
    return os.path.normpath(caminho if os.path.isabs(caminho) else os.path.join(cwd, caminho))


def novo_cwd_do_cd(args, cwd):
    """cwd efetivo depois de um `cd` (args já sem o próprio `cd`)."""
    alvos = [a for a in args if not a.startswith("-")]
    if not alvos:
        return cwd if args else os.path.expanduser("~")
    return resolve(alvos[0], cwd)
