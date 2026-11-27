"""Decisão compartilhada de "esta sessão pode escrever neste caminho?".

Usada por DOIS hooks, para que a regra não diverja com o tempo:
  - deny-orchestrator-code-edits.sh   (Write|Edit)
  - deny-orchestrator-bash-writes.py  (Bash: redirecionamento, tee, sed -i, cp/mv/install)

TRÊS MODOS, detectados pela raiz da sessão (cwd do payload, senão CLAUDE_PROJECT_DIR):
  fábrica     — raiz tem `projects/` E `templates/prompt.template.md` (layout do
                Forge como fábrica standalone). Allowlist: */.forge/*, */prompt.md,
                */templates/*, *.md, *.markdown — em qualquer lugar do repo.
  projeto da fábrica
              — a raiz (ou algum ancestral dela, P) está em `<F>/projects/<nome>` e F é uma
                fábrica. É a sessão aberta direto no projeto. Orquestrador: dentro de P vale a
                allowlist do "repo atual" (raiz = P). FORA de P só passa o que não é código:
                *.md/*.markdown, prompt.md, qualquer caminho dentro de uma pasta `.forge/` e os
                artefatos abaixo, além de /tmp, $TMPDIR e as pastas `~/.claude*` (memória, planos),
                por realpath — estas últimas nunca valem para o que estiver dentro da própria
                fábrica F. Não há contenção: código fora de P é negado pelo mesmo motivo de
                código de sempre (delegue ao subagente dev). Subagentes escrevem livremente.
  repo atual  — qualquer outro caso, ou seja, o Forge (como plugin) rodando dentro do
                repositório de trabalho de alguém. O orquestrador só pode escrever em
                `.forge/**` NA RAIZ do repo, em `*.md`/`*.markdown` e em `prompt.md`, além dos
                dois liberados gerais e da exceção do /forge:setup abaixo. Não pode escrever
                código-fonte. Subagentes escrevem livremente (os hooks saem cedo).

Em TODOS os modos o subagente (payload com `agent_id`) escreve livremente, em qualquer lugar.

DOIS LIBERADOS GERAIS, nos modos fábrica e repo atual (checados antes da allowlist do modo):
  - Fora da raiz do projeto: o caminho é resolvido com `os.path.realpath` (então `..` e symlinks
    não enganam) e, se cair fora da raiz, não é código deste projeto — scratchpad do Claude Code
    (/tmp/claude-*/.../scratchpad/), /tmp, memória em ~/.claude. O runtime manda usar o
    scratchpad para temporários; barrar isso só atrapalha. Um `..` que volta para dentro da raiz
    continua dentro, e é avaliado normalmente. (No modo projeto da fábrica isto NÃO vale: fora
    de P só passa o que não é código, como listado acima.)
  - Artefatos que não são código: *.log, *.patch, *.diff, *.out, *.txt, em qualquer lugar.
    Exceção: requirements*.txt, que é dependência de projeto Python.

EXCEÇÃO DO /forge:setup: o próprio comando precisa criar, NA RAIZ do projeto, os arquivos que
fazem o Forge funcionar ali (.gitignore, .claude/settings.json, .claude/settings.local.json, projects/.gitkeep, templates/.npmrc). Sem esta
exceção o setup é barrado pelo hook do próprio Forge, e o agente poderia contornar escrevendo
por `Bash`. A exceção é estreita de propósito: só estes nomes, só na raiz. Duas checagens:
  - _exato: a raiz JÁ EXISTE — compara relpath contra `root`. Usada sempre, nos três modos.
  - _nova_fabrica: o usuário pediu a fábrica em OUTRO caminho (raiz nova ainda inexistente) —
    casa pelo SUFIXO do caminho. Só no modo "repo atual": nos outros modos a exceção não pode
    vazar para `projects/x/...` nem `sub/...`.
"""
import fnmatch
import os
from typing import NamedTuple

CONFIG_DO_SETUP = {".gitignore", os.path.join(".claude", "settings.json"),
                   os.path.join(".claude", "settings.local.json"),
                   os.path.join("projects", ".gitkeep"),
                   os.path.join("templates", ".npmrc")}


def raiz_do_payload(payload):
    """Cwd do payload (mais confiável), senão CLAUDE_PROJECT_DIR, senão o cwd do processo."""
    root = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return os.path.abspath(root)


def _eh_config_do_setup_exato(file_path, root):
    caminho = file_path if os.path.isabs(file_path) else os.path.join(root, file_path)
    try:
        rel = os.path.relpath(os.path.normpath(caminho), root)
    except ValueError:
        return False
    return rel in CONFIG_DO_SETUP


def _eh_config_do_setup_nova_fabrica(file_path, root):
    caminho = file_path if os.path.isabs(file_path) else os.path.join(root, file_path)
    caminho = os.path.normpath(caminho)
    return any(caminho == cfg or caminho.endswith(os.sep + cfg) for cfg in CONFIG_DO_SETUP)


ARTEFATOS_LIVRES = ("*.log", "*.patch", "*.diff", "*.out", "*.txt")


def _eh_artefato_livre(file_path):
    nome = os.path.basename(file_path).lower()
    if fnmatch.fnmatch(nome, "requirements*.txt"):
        return False
    return any(fnmatch.fnmatch(nome, g) for g in ARTEFATOS_LIVRES)


def _fora_da_raiz(abs_file, root):
    try:
        return os.path.commonpath([abs_file, root]) != root
    except ValueError:
        return True


def _eh_fabrica(root):
    return (os.path.isdir(os.path.join(root, "projects"))
            and os.path.isfile(os.path.join(root, "templates", "prompt.template.md")))


def avalia_caminho(file_path, root):
    """Devolve (liberado, modo, permitido_desc) para o orquestrador escrever em file_path."""
    root = os.path.realpath(root)
    file_path = os.path.realpath(file_path if os.path.isabs(file_path)
                                 else os.path.join(root, file_path))
    livre = _fora_da_raiz(file_path, root) or _eh_artefato_livre(file_path)
    liberado, modo, permitido_desc = _avalia_dentro_da_raiz(file_path, root)
    return liberado or livre, modo, permitido_desc


def _avalia_dentro_da_raiz(file_path, root):
    if _eh_fabrica(root):
        modo = "fábrica"
        permitido_desc = (
            "prompt.md, .forge/*, templates/*, *.md/*.markdown (em qualquer lugar do repo — "
            "detectado por projects/ + templates/prompt.template.md na raiz), mais os arquivos de "
            "configuração que o /forge:setup cria na raiz (.gitignore, .claude/settings.json, .claude/settings.local.json, projects/.gitkeep, templates/.npmrc); "
            "em qualquer modo também é livre tudo FORA da raiz do projeto (scratchpad, /tmp, ~/.claude) "
            "e os artefatos *.log/*.patch/*.diff/*.out/*.txt (exceto requirements*.txt)"
        )
        allow = ["*/.forge/*", "*/prompt.md", "*/templates/*", "*.md", "*.markdown"]
        liberado = (any(fnmatch.fnmatch(file_path, g) for g in allow)
                    or _eh_config_do_setup_exato(file_path, root))
        return liberado, modo, permitido_desc

    modo = "repo atual"
    permitido_desc = (
        "escrever em .forge/** na raiz do repo, em *.md/*.markdown, em prompt.md, e nos arquivos de "
        "configuração que o /forge:setup cria na raiz (.gitignore, .claude/settings.json, .claude/settings.local.json, projects/.gitkeep, templates/.npmrc; "
        "também na raiz de uma fábrica nova, ainda inexistente, pelo sufixo do caminho); "
        "também é livre tudo FORA da raiz do projeto (scratchpad, /tmp, ~/.claude) e os artefatos "
        "*.log/*.patch/*.diff/*.out/*.txt (exceto requirements*.txt) — nunca código-fonte"
    )
    return _allowlist_do_repo(file_path, root, setup_em_fabrica_nova=True), modo, permitido_desc


def _allowlist_do_repo(file_path, root, setup_em_fabrica_nova):
    """Allowlist do orquestrador num repo de trabalho: .forge/** na raiz, markdown, prompt.md, setup."""
    abs_file = file_path if os.path.isabs(file_path) else os.path.join(root, file_path)
    abs_file = os.path.normpath(abs_file)
    forge_dir = os.path.normpath(os.path.join(root, ".forge"))
    dentro_do_forge = abs_file == forge_dir or abs_file.startswith(forge_dir + os.sep)
    eh_markdown = fnmatch.fnmatch(file_path, "*.md") or fnmatch.fnmatch(file_path, "*.markdown")
    eh_prompt = os.path.basename(file_path) == "prompt.md"
    return (dentro_do_forge or eh_markdown or eh_prompt
            or _eh_config_do_setup_exato(file_path, root)
            or (setup_em_fabrica_nova and _eh_config_do_setup_nova_fabrica(file_path, root)))


MODO_PROJETO = "projeto da fábrica"


class Decisao(NamedTuple):
    liberado: bool
    modo: str = ""
    permitido_desc: str = ""


def contexto_projeto_da_fabrica(root):
    """(P, F) se a raiz da sessão está dentro de `<F>/projects/<nome>` e F é fábrica; senão None.

    Sobe pelos ancestrais (a própria raiz inclusa), pelo caminho real. Se a raiz já é uma
    fábrica, o modo é "fábrica" e devolve None.
    """
    atual = os.path.realpath(root)
    if _eh_fabrica(atual):
        return None
    while True:
        pai = os.path.dirname(atual)
        if pai == atual:
            return None
        if os.path.basename(pai) == "projects":
            fabrica = os.path.dirname(pai)
            if _eh_fabrica(fabrica):
                return atual, fabrica
        atual = pai


def _bases_livres_fora_do_projeto():
    """Pastas (realpath) onde se escreve de fora do projeto: /tmp, $TMPDIR, ~/.claude*."""
    bases = [os.path.realpath("/tmp")]
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        bases.append(os.path.realpath(tmpdir))
    home = os.path.expanduser("~")
    try:
        nomes = os.listdir(home)
    except OSError:
        nomes = []
    for nome in nomes:
        pasta = os.path.join(home, nome)
        if nome.startswith(".claude") and os.path.isdir(pasta):
            bases.append(os.path.realpath(pasta))
    return [b for b in bases if b != os.sep]


def _eh_excecao_fora_do_projeto(real, fabrica):
    if not _fora_da_raiz(real, fabrica):
        return False  # a própria fábrica nunca entra nas exceções (ex.: fábrica dentro de /tmp)
    return any(not _fora_da_raiz(real, base) for base in _bases_livres_fora_do_projeto())


def _eh_nao_codigo_fora_do_projeto(real):
    """Markdown, prompt.md, qualquer coisa dentro de uma pasta `.forge/` e os artefatos."""
    pastas = os.path.dirname(real).split(os.sep)
    eh_markdown = fnmatch.fnmatch(real, "*.md") or fnmatch.fnmatch(real, "*.markdown")
    return (eh_markdown or os.path.basename(real) == "prompt.md" or ".forge" in pastas
            or _eh_artefato_livre(real))


def _avalia_no_projeto(real, projeto, fabrica):
    permitido_desc = (
        f"dentro do projeto ({projeto}): .forge/** na raiz do projeto, *.md/*.markdown, prompt.md, "
        "a configuração do /forge:setup e os artefatos *.log/*.patch/*.diff/*.out/*.txt "
        "(exceto requirements*.txt); fora dele: *.md/*.markdown, prompt.md, qualquer pasta .forge/, "
        "os mesmos artefatos, /tmp e ~/.claude* — nunca código-fonte"
    )
    if _fora_da_raiz(real, projeto):
        liberado = (_eh_excecao_fora_do_projeto(real, fabrica)
                    or _eh_nao_codigo_fora_do_projeto(real))
    else:
        liberado = (_allowlist_do_repo(real, projeto, setup_em_fabrica_nova=False)
                    or _eh_artefato_livre(real))
    return Decisao(liberado, MODO_PROJETO, permitido_desc)


def avalia_escrita(file_path, root, subagente=False):
    """Decide se a sessão (orquestrador ou subagente) pode escrever em file_path.

    O subagente é sempre liberado, em qualquer modo. O orquestrador segue `avalia_caminho`
    (fábrica e repo atual) ou a regra do modo projeto da fábrica descrita no cabeçalho.
    Caminho relativo é resolvido contra `root` (a raiz/cwd da sessão).
    """
    if subagente:
        return Decisao(True)
    ctx = contexto_projeto_da_fabrica(root)
    if ctx is None:
        liberado, modo, permitido_desc = avalia_caminho(file_path, root)
        return Decisao(liberado, modo, permitido_desc)
    base = os.path.realpath(root)
    real = os.path.realpath(file_path if os.path.isabs(file_path)
                            else os.path.join(base, file_path))
    return _avalia_no_projeto(real, ctx[0], ctx[1])
