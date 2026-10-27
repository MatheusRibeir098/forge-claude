"""Decisão compartilhada de "o orquestrador pode escrever neste caminho?".

Usada por DOIS hooks, para que a regra não diverja com o tempo:
  - deny-orchestrator-code-edits.sh   (Write|Edit)
  - deny-orchestrator-bash-writes.py  (Bash: redirecionamento, tee, sed -i, cp/mv/install)

DOIS MODOS, detectados pela raiz do projeto (cwd do payload, senão CLAUDE_PROJECT_DIR):
  fábrica     — raiz tem `projects/` E `templates/prompt.template.md` (layout do
                Forge como fábrica standalone). Allowlist: */.forge/*, */prompt.md,
                */templates/*, *.md, *.markdown — em qualquer lugar do repo.
  repo atual  — qualquer outro caso, ou seja, o Forge (como plugin) rodando dentro do
                repositório de trabalho de alguém. O orquestrador só pode escrever em
                `.forge/**` NA RAIZ do repo, em `*.md`/`*.markdown` e em `prompt.md`, além dos
                dois liberados gerais e da exceção do /forge:setup abaixo. Não pode escrever
                código-fonte.

DOIS LIBERADOS GERAIS, nos dois modos (checados antes da allowlist do modo):
  - Fora da raiz do projeto: o caminho é resolvido com `os.path.realpath` (então `..` e symlinks
    não enganam) e, se cair fora da raiz, não é código deste projeto — scratchpad do Claude Code
    (/tmp/claude-*/.../scratchpad/), /tmp, memória em ~/.claude. O runtime manda usar o
    scratchpad para temporários; barrar isso só atrapalha. Um `..` que volta para dentro da raiz
    continua dentro, e é avaliado normalmente.
  - Artefatos que não são código: *.log, *.patch, *.diff, *.out, *.txt, em qualquer lugar.
    Exceção: requirements*.txt, que é dependência de projeto Python.

EXCEÇÃO DO /forge:setup: o próprio comando precisa criar, NA RAIZ do projeto, os arquivos que
fazem o Forge funcionar ali (.gitignore, .claude/settings.json, .claude/settings.local.json, projects/.gitkeep, templates/.npmrc). Sem esta
exceção o setup é barrado pelo hook do próprio Forge, e o agente poderia contornar escrevendo
por `Bash`. A exceção é estreita de propósito: só estes nomes, só na raiz. Duas checagens:
  - _exato: a raiz JÁ EXISTE — compara relpath contra `root`. Usada sempre, nos dois modos.
  - _nova_fabrica: o usuário pediu a fábrica em OUTRO caminho (raiz nova ainda inexistente) —
    casa pelo SUFIXO do caminho. Só no modo "repo atual": no modo fábrica a exceção não pode
    vazar para `projects/x/...` nem `sub/...`.
"""
import fnmatch
import os

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
    abs_file = file_path if os.path.isabs(file_path) else os.path.join(root, file_path)
    abs_file = os.path.normpath(abs_file)
    forge_dir = os.path.normpath(os.path.join(root, ".forge"))
    dentro_do_forge = abs_file == forge_dir or abs_file.startswith(forge_dir + os.sep)
    eh_markdown = fnmatch.fnmatch(file_path, "*.md") or fnmatch.fnmatch(file_path, "*.markdown")
    eh_prompt = os.path.basename(file_path) == "prompt.md"
    liberado = (dentro_do_forge or eh_markdown or eh_prompt
                or _eh_config_do_setup_exato(file_path, root)
                or _eh_config_do_setup_nova_fabrica(file_path, root))
    return liberado, modo, permitido_desc
