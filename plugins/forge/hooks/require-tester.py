#!/usr/bin/env python3
"""Obrigação do `tester` depois de cada `dev`: decide se a entrega precisa de validação, em que
modo, e não deixa o orquestrador encerrar o turno com entrega sem `tester`.

TRÊS EVENTOS, UM ESTADO POR SESSÃO (o script despacha por `hook_event_name`)
Na CLI 2.1.331 todo `Agent` lançado pela raiz é ASSÍNCRONO: o `PostToolUse(Agent)` dispara no
lançamento com `tool_response` = {"isAsync": true, "status": "async_launched"} e o retorno chega
depois, como notificação. Por isso a decisão saiu do `PostToolUse` e foi para o `SubagentStop`:
  SubagentStop — dispara em QUALQUER profundidade (Workflow, agente aninhado), com `agent_id`,
      `agent_type`, `last_assistant_message` e `agent_transcript_path`. `dev`: classifica o
      retorno e anota a entrega pendente. `tester`: aplica o veredito. NUNCA imprime nada:
      saída de SubagentStop manteria o SUBAGENTE rodando (doc oficial), não fala com a raiz.
      Repete para o mesmo `agent_id` quando o agente é retomado (ex.: depois de esperar um
      filho) — daí a deduplicação por `agent_id` + assinatura do contrato.
  PostToolUse(Agent) na raiz — `async_launched` de `tester` marca "tester em andamento".
      `completed` (CLIs antigas, lançamento síncrono, verificado na 2.1.272 com as fixtures
      `posttooluse-agent-completed*`) segue como antes: classifica, anota pelo MESMO estado e
      injeta o lembrete com `additionalContext`.
  Stop (raiz) — com entrega pendente ainda não cobrada, sem `tester` em andamento e sem
      subagente do Forge em voo, devolve {"decision": "block", "reason": ...}: o orquestrador
      despacha o `tester` ou explica ao usuário por que não. Com `stop_hook_active` libera
      sempre (nunca entra em laço) e cada entrega é cobrada UMA vez (o campo `cobrado`), para
      a guarda não virar ladainha a cada turno depois de o usuário ter decidido.
O retorno do `dev` vem tipicamente dentro de uma cerca ```json com texto solto em volta; o
parser abaixo tolera cerca e prosa. Agente de workflow (`forge:executar-lote`, `forge:investigar`)
roda com `schema` e entrega o retorno pela ferramenta `StructuredOutput`: sem contrato no texto,
o SubagentStop usa o último `StructuredOutput` do `agent_transcript_path` (o texto tem prioridade).

POR QUE ISSO IMPORTA — o custo do palpite pela entrada
Decidir por uma lista de palavras genéricas (`dashboard`, `layout`, `tela`, `botão`,
`rota`…) dispararia o lembrete mesmo em projetos sem UI nenhuma (um servidor MCP, um
compilador), e um regex de "API" casaria `src/adapters/foo.ts` dentro de `mcp-server/` só
porque a string contém "server". O lembrete viraria ruído e passaria a ser ignorado TAMBÉM
quando fosse legítimo. Um lembrete que mente é pior que nenhum.

Por isso só existe um sinal e ele é factual: a lista `arquivos_alterados` que o próprio `dev`
devolveu, mais os `comandos_para_subir`. Três saídas:
  browser  — há arquivo renderizável (.tsx .jsx .vue .svelte .html .css .scss .astro) E há
             comando para subir. É o ÚNICO caso em que se fala em print.
  contrato — superfície externa verificável sem navegador: caminho que indica servidor /
             handler / tool MCP / rota / API / schema / migration, `.yaml`/`.yml` aplicado,
             ou comandos para subir sem nada renderizável.
  silêncio — refactor puro, teste, documentação, config de build, tipos. E também
             `status: "BLOQUEADO"` (não há entrega para validar).

Casamento por FRONTEIRA de caminho, nunca por substring: o caminho é quebrado em tokens
(`/ - _ .`) e comparado a um conjunto fechado. Assim `mcp-server`, `mcp_server`,
`server.test.ts` e `vite.config.ts` não disparam `browser` — teste e config de build são
descartados antes de qualquer classificação, e "renderizável" é decidido pela EXTENSÃO final,
não por palavra no meio do nome.

Se o `dev` não seguir o contrato JSON, cai para a heurística pelo briefing — mas só por nome
de arquivo com extensão renderizável, sem a lista de palavras genéricas que geraria ruído. O
texto injetado avisa que foi fallback.

ORDEM DOS EVENTOS E OS TRÊS VEREDITOS DO TESTER
Cada entrega pendente é {agent_id, modo, arquivos, resumo, cobrado}, uma por `dev`:
  - retorno do `dev` que exige validação -> anota a entrega (reabre, mesmo após um PASSOU);
  - `tester` PASSOU    -> remove as entregas cujos arquivos o briefing do `tester` cita; se
                          nenhuma casar, remove a mais antiga (só cobre o que veio ANTES dele);
  - `tester` FALHOU    -> mantém e anota o resumo das falhas: devolver ao `dev` e revalidar;
  - `tester` BLOQUEADO -> mantém e anota o motivo: NÃO é aprovação; resolver o ambiente ou
                          perguntar ao usuário, nunca seguir adiante.

Saída silenciosa (exit 0) em qualquer payload ilegível: um hook nunca atrapalha o trabalho.
No `PostToolUse` e no `Stop` só a sessão-raiz orquestra, daí a guarda `agent_id`.
"""
import collections
import contextlib
import hashlib
import itertools
import json
import os
import pathlib
import re
import sys
import time

try:
    import fcntl
except ImportError:  # Windows: sem trava, o estado só perde a garantia contra corrida
    fcntl = None

# --- classificação de caminho ------------------------------------------------------------

EXT_RENDERIZAVEL = (".tsx", ".jsx", ".vue", ".svelte", ".html", ".css", ".scss", ".astro")
EXT_DOC = (".md", ".mdx", ".rst", ".adoc", ".txt")

# teste: diretório de teste, prefixo test_ (Python) ou sufixo .test./.spec.
RE_TESTE = re.compile(
    r"(?:^|/)(?:tests?|__tests__|spec|specs|e2e|cypress|playwright)/"
    r"|(?:^|/)test_[^/]+$"
    r"|[._-](?:test|spec)\.[A-Za-z0-9]+$"
    r"|\.stories\.[A-Za-z0-9]+$",
    re.I,
)

# config de build / tooling / lockfile / CI — nunca é entrega validável
RE_BUILD = re.compile(
    r"(?:^|/)\.github/"
    r"|(?:^|/)(?:"
    r"(?:vite|vitest|webpack|rollup|jest|tailwind|postcss|babel|next|nuxt|svelte|astro"
    r"|esbuild|tsup|karma|cypress|playwright)\.config\.[cm]?[jt]s"
    r"|eslint\.config\.[cm]?[jt]s|\.eslintrc[\w.-]*|\.prettierrc[\w.-]*"
    r"|tsconfig(?:\.[\w-]+)?\.json|jsconfig\.json"
    r"|package(?:-lock)?\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|uv\.lock"
    r"|pyproject\.toml|setup\.(?:py|cfg)|requirements[\w.-]*\.txt"
    r"|Makefile|\.gitignore|\.editorconfig|\.npmrc|\.nvmrc"
    r")$",
    re.I,
)

# tipos puros — não têm comportamento para validar
RE_TIPOS = re.compile(r"\.d\.ts$|(?:^|/)types?/|(?:^|/)types?\.[cm]?[jt]s$", re.I)

# tokens de superfície externa; comparados contra o caminho quebrado em fronteiras
TOKENS_CONTRATO = frozenset({
    "server", "servers", "handler", "handlers", "route", "routes", "router", "routers",
    "api", "apis", "endpoint", "endpoints", "controller", "controllers", "middleware",
    "mcp", "tool", "tools", "resolver", "resolvers", "graphql", "rest", "rpc", "grpc",
    "schema", "schemas", "migration", "migrations", "migrate", "seed", "seeds",
    "lambda", "lambdas", "webhook", "webhooks", "cli", "daemon", "worker", "workers",
})

RE_SEPARADOR = re.compile(r"[^A-Za-z0-9]+")


def _tokens(caminho: str) -> set:
    return {t for t in RE_SEPARADOR.split(caminho.lower()) if t}


def _descartavel(caminho: str) -> bool:
    """Teste, documentação, config de build ou tipo puro: não há superfície para validar."""
    c = caminho.strip().replace("\\", "/")
    if not c:
        return True
    if RE_TESTE.search(c) or RE_BUILD.search(c) or RE_TIPOS.search(c):
        return True
    return c.lower().endswith(EXT_DOC)


def _renderizavel(caminho: str) -> bool:
    """Decidido pela EXTENSÃO final — `mcp-server`/`server.test.ts` nunca entram aqui."""
    return caminho.strip().replace("\\", "/").lower().endswith(EXT_RENDERIZAVEL)


def _superficie_externa(caminho: str) -> bool:
    c = caminho.strip().replace("\\", "/")
    if c.lower().endswith((".yaml", ".yml")):
        return True  # config aplicada (dashboard, pipeline, manifesto)
    return bool(_tokens(c) & TOKENS_CONTRATO)


# --- extração do retorno do dev ----------------------------------------------------------

RE_CERCA = re.compile(r"```[A-Za-z0-9_-]*[ \t]*\r?\n(.*?)```", re.S)


def _objetos_balanceados(texto: str):
    """Todo `{...}` de chaves balanceadas, respeitando string e escape."""
    i, n = 0, len(texto)
    while i < n:
        if texto[i] != "{":
            i += 1
            continue
        prof, em_string, escape, j = 0, False, False, i
        while j < n:
            c = texto[j]
            if em_string:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    em_string = False
            elif c == '"':
                em_string = True
            elif c == "{":
                prof += 1
            elif c == "}":
                prof -= 1
                if prof == 0:
                    yield texto[i:j + 1]
                    break
            j += 1
        i = j + 1


def _candidatos(texto: str):
    for m in RE_CERCA.finditer(texto):
        yield m.group(1)
    for bruto in _objetos_balanceados(texto):
        yield bruto


def _retorno_do_dev(texto: str):
    """Primeiro objeto que se pareça com o contrato do `dev`; None se ele não o seguiu."""
    reserva = None
    for bruto in _candidatos(texto):
        try:
            obj = json.loads(bruto)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        if "arquivos_alterados" in obj:
            return obj
        if reserva is None and "status" in obj and "comandos_para_subir" in obj:
            reserva = obj
        elif reserva is None and str(obj.get("status") or "").upper() == "BLOQUEADO":
            reserva = obj
    return reserva


def _texto_do_retorno(resp: dict) -> str:
    partes = []
    for bloco in resp.get("content") or []:
        if isinstance(bloco, dict) and isinstance(bloco.get("text"), str):
            partes.append(bloco["text"])
        elif isinstance(bloco, str):
            partes.append(bloco)
    return "\n".join(partes)


def _lista_de_strings(valor) -> list:
    saida = []
    for item in valor if isinstance(valor, list) else []:
        if isinstance(item, str):
            texto = item.strip()
        elif isinstance(item, dict):
            texto = str(item.get("path") or item.get("arquivo") or item.get("file") or "").strip()
        else:
            texto = ""
        if texto:
            saida.append(texto)
    return saida


# --- estado: as entregas sem validação, por sessão ----------------------------------------
# Mesmo esquema do `delega-varredura.py` e do `subagent-turn-budget.sh`: `FORGE_STATE_DIR`
# explícito > `XDG_RUNTIME_DIR` > `TMPDIR` > `/tmp`, sob `forge/validacao/<session_id>`.
# Agentes aninhados mantêm o `session_id` da raiz, então o estado é um só em qualquer
# profundidade. Arquivos:
#   pendente            {"entregas": [...], "ultimo_veredito": {...}}; existe só com entrega
#   vistos.json         {"<papel>:<agent_id>": assinatura} — dedup do SubagentStop repetido
#   tester-em-andamento marcado no lançamento assíncrono do `tester`, com validade
#   .trava              flock: dois `dev` em paralelo terminam juntos

RE_SESSAO_INVALIDA = re.compile(r"[^A-Za-z0-9_-]")
ARQUIVO_PENDENTE = "pendente"
ARQUIVO_VISTOS = "vistos.json"
ARQUIVO_TESTER = "tester-em-andamento"
ARQUIVO_TRAVA = ".trava"
IDADE_MAXIMA_S = 24 * 3600
IDADE_TESTER_S = 2 * 3600  # tester que morreu sem SubagentStop não cala a guarda para sempre
TETO_ENTREGAS = 100
TETO_VISTOS = 200
VEREDITOS = ("PASSOU", "FALHOU", "BLOQUEADO")
SEM_CONTRATO = "sem-contrato"
VEREDITO_APLICADO = "veredito"
NOME_SAIDA_ESTRUTURADA = "StructuredOutput"

Decisao = collections.namedtuple("Decisao", "modo texto arquivos resumo")


def _diretorio_de_estado(session_id) -> pathlib.Path:
    explicito = os.environ.get("FORGE_STATE_DIR")
    if explicito:
        return pathlib.Path(explicito)
    base = os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("TMPDIR") or "/tmp"
    sessao = RE_SESSAO_INVALIDA.sub("", session_id)[:120] if isinstance(session_id, str) else ""
    corpo = pathlib.Path(base) / "forge" / "validacao"
    return corpo / sessao if sessao else corpo


def _limpar_antigos(pasta: pathlib.Path) -> None:
    limite = time.time() - IDADE_MAXIMA_S
    for item in pasta.iterdir():
        try:
            if item.name != ARQUIVO_TRAVA and item.is_file() and item.stat().st_mtime < limite:
                item.unlink()
        except OSError:
            continue


def _ler_json(caminho: pathlib.Path) -> dict:
    try:
        valor = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return valor if isinstance(valor, dict) else {}


def _gravar_json(caminho: pathlib.Path, valor: dict) -> None:
    caminho.write_text(json.dumps(valor, ensure_ascii=False), encoding="utf-8")


class _Estado:
    """Entregas pendentes, último veredito e assinaturas já vistas de uma sessão."""

    def __init__(self, pasta: pathlib.Path):
        self.pasta = pasta
        dados = _ler_json(pasta / ARQUIVO_PENDENTE)
        self.entregas = [e for e in dados.get("entregas") or [] if isinstance(e, dict)]
        veredito = dados.get("ultimo_veredito")
        self.ultimo_veredito = veredito if isinstance(veredito, dict) else None
        self.vistos = _ler_json(pasta / ARQUIVO_VISTOS)

    def trocar_entrega(self, agent_id: str, decisao) -> None:
        """A entrega de um `agent_id` é sempre a do último retorno dele (agente retomado)."""
        if agent_id:
            self.entregas = [e for e in self.entregas if e.get("agent_id") != agent_id]
        if decisao is not None:
            self.entregas.append({"agent_id": agent_id, "modo": decisao.modo,
                                  "arquivos": decisao.arquivos[:20],
                                  "resumo": decisao.resumo, "cobrado": False})

    def remover(self, removidas: list) -> None:
        self.entregas = [e for e in self.entregas if e not in removidas]

    def gravar(self) -> None:
        try:
            if self.entregas:
                _gravar_json(self.pasta / ARQUIVO_PENDENTE, {
                    "entregas": self.entregas[-TETO_ENTREGAS:],
                    "ultimo_veredito": self.ultimo_veredito})
            else:
                (self.pasta / ARQUIVO_PENDENTE).unlink(missing_ok=True)
            _gravar_json(self.pasta / ARQUIVO_VISTOS,
                         dict(list(self.vistos.items())[-TETO_VISTOS:]))
        except OSError:
            return


@contextlib.contextmanager
def _estado_travado(pasta: pathlib.Path):
    """Lê sob trava exclusiva e regrava ao sair. Falha de disco nunca atrapalha: sem estado o
    hook só perde a memória."""
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        _limpar_antigos(pasta)
        trava = open(pasta / ARQUIVO_TRAVA, "a", encoding="utf-8")
    except OSError:
        yield _Estado(pasta)
        return
    with trava:
        if fcntl is not None:
            fcntl.flock(trava.fileno(), fcntl.LOCK_EX)
        estado = _Estado(pasta)
        yield estado
        estado.gravar()


def _marcar_tester_em_andamento(pasta: pathlib.Path) -> None:
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / ARQUIVO_TESTER).write_text(str(time.time()), encoding="utf-8")
    except OSError:
        return


def _limpar_tester_em_andamento(pasta: pathlib.Path) -> None:
    try:
        (pasta / ARQUIVO_TESTER).unlink(missing_ok=True)
    except OSError:
        return


def _tester_marcado(pasta: pathlib.Path) -> bool:
    try:
        return time.time() - (pasta / ARQUIVO_TESTER).stat().st_mtime < IDADE_TESTER_S
    except OSError:
        return False


def _subagente_do_forge_em_voo(background_tasks) -> bool:
    """`dev`/`tester` ainda rodando: a raiz acorda de novo quando ele terminar, e o próximo
    Stop reavalia. Cobrar agora seria cobrar retrato intermediário."""
    for tarefa in background_tasks if isinstance(background_tasks, list) else []:
        if isinstance(tarefa, dict) and _papel_do_agente(tarefa.get("agent_type")) in (
                "dev", "tester"):
            return True
    return False


def _assinatura(retorno) -> str:
    if not isinstance(retorno, dict):
        return SEM_CONTRATO
    canonico = json.dumps(retorno, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(canonico.encode("utf-8")).hexdigest()[:16]


def _registrar_dev(pasta: pathlib.Path, agent_id: str, retorno, decisao) -> None:
    """Anota (ou troca) a entrega do `agent_id`. Repetição da mesma assinatura não muda nada,
    e retorno fora do contrato nunca rebaixa um agente que já devolveu contrato."""
    chave = f"dev:{agent_id}"
    assinatura = _assinatura(retorno)
    with _estado_travado(pasta) as estado:
        anterior = estado.vistos.get(chave) if agent_id else None
        if anterior == assinatura or (assinatura == SEM_CONTRATO and anterior is not None):
            return
        if agent_id:
            estado.vistos[chave] = assinatura
        estado.trocar_entrega(agent_id, decisao)


def _citado(arquivo: str, briefing: str) -> bool:
    """Até os dois últimos segmentos do caminho: o briefing do `tester` raramente repete a
    raiz que o `dev` usou, e só o nome (`index.ts`) casaria demais."""
    sufixo = "/".join(arquivo.replace("\\", "/").split("/")[-2:])
    return bool(sufixo) and sufixo in briefing


def _entregas_cobertas(entregas: list, briefing: str) -> list:
    cobertas = [e for e in entregas
                if any(_citado(a, briefing) for a in e.get("arquivos") or [])]
    return cobertas or entregas[:1]


def _resumo_veredito(veredito: str, retorno: dict) -> str:
    if veredito == "BLOQUEADO":
        bloqueio = retorno.get("bloqueio") if isinstance(retorno.get("bloqueio"), dict) else {}
        motivo = bloqueio.get("o_que_impediu")
    else:
        motivo = retorno.get("recomendacao_para_dev")
    return _corte(motivo or _resumo_falhas(retorno) or "sem detalhe", 160)


def _registrar_veredito(pasta: pathlib.Path, agent_id: str, retorno, ler_briefing) -> bool:
    """Aplica o veredito uma vez por `agent_id`. Devolve se havia entrega pendente antes."""
    chave = f"tester:{agent_id}"
    with _estado_travado(pasta) as estado:
        havia = bool(estado.entregas)
        if retorno is None or (agent_id and estado.vistos.get(chave) == VEREDITO_APLICADO):
            return havia  # sem veredito (talvez intermediário) ou repetição
        if agent_id:
            estado.vistos[chave] = VEREDITO_APLICADO
        veredito = str(retorno.get("veredito")).strip().upper()
        if veredito == "PASSOU":
            estado.remover(_entregas_cobertas(estado.entregas, ler_briefing()))
            estado.ultimo_veredito = None
            return havia
        estado.ultimo_veredito = {"veredito": veredito,
                                  "resumo": _resumo_veredito(veredito, retorno)}
        for entrega in estado.entregas:
            entrega["cobrado"] = False  # reprovação reabre a cobrança no próximo Stop
        return havia


# --- texto injetado ----------------------------------------------------------------------

def _resumo_lista(itens: list, teto: int = 5) -> str:
    if not itens:
        return "(nenhum)"
    corpo = ", ".join(itens[:teto])
    return corpo + (f" … (+{len(itens) - teto})" if len(itens) > teto else "")


def _bloco_comandos(comandos: list) -> str:
    if not comandos:
        return ("comandos_para_subir: o `dev` não devolveu nenhum — peça-os a ele ou mande o "
                "`tester` descobrir como subir antes de validar.")
    linhas = "\n".join(f"  $ {c}" for c in comandos)
    return f"comandos_para_subir (literais, como o `dev` devolveu):\n{linhas}"


AVISO = ("Avise o usuário em UMA linha o que você vai validar e por quê — decida, não "
         "pergunte. Se houver outro `dev` liberado, dispare-o na mesma mensagem do `tester` "
         "para rodarem em paralelo.")

BLOQUEIO = ("O `dev` está bloqueado por hook de subir servidor e rodar E2E — sem "
            "o `tester` esta tarefa simplesmente não foi validada por ninguém.")


def _emitir(texto: str) -> int:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": texto,
    }}))
    return 0


def _texto_browser(arquivos: list, comandos: list, renderizaveis: list) -> str:
    return (
        "[validação pendente — modo browser] O `dev` terminou e alterou arquivo renderizável "
        f"({_resumo_lista(renderizaveis, 3)}) com comando para subir. Invoque o `tester` em "
        "modo browser ANTES de marcar a tarefa como concluída em tasks.md: ele sobe a "
        "aplicação, navega e tira print (teto explícito de 5). " + BLOQUEIO + "\n"
        f"arquivos_alterados: {_resumo_lista(arquivos)}\n"
        f"{_bloco_comandos(comandos)}\n" + AVISO
    )


def _texto_contrato(arquivos: list, comandos: list, motivo: str) -> str:
    return (
        f"[validação pendente — modo contrato] O `dev` terminou e {motivo}, sem nada "
        "renderizável em navegador. Invoque o `tester` em modo contrato ANTES de marcar a "
        "tarefa como concluída em tasks.md: exercitar a superfície por chamada REAL (subir o "
        "processo, `curl`/CLI/cliente MCP, aplicar o schema ou a migration) e conferir contra "
        "o contrato. " + BLOQUEIO + "\n"
        f"arquivos_alterados: {_resumo_lista(arquivos)}\n"
        f"{_bloco_comandos(comandos)}\n" + AVISO
    )


# --- fallback pelo briefing --------------------------------------------------------------

RE_ARQ_RENDERIZAVEL = re.compile(
    r"[\w./@-]+\.(?:tsx|jsx|vue|svelte|html|css|scss|astro)\b", re.I)


def _briefing_da_entrada(inp: dict) -> str:
    return " ".join(str(inp.get(k) or "") for k in ("prompt", "description"))


LINHAS_ATE_O_BRIEFING = 50


def _texto_de_usuario(linha: str) -> str:
    try:
        registro = json.loads(linha)
    except ValueError:
        return ""
    mensagem = registro.get("message") if isinstance(registro, dict) else None
    if not isinstance(mensagem, dict) or mensagem.get("role") != "user":
        return ""
    conteudo = mensagem.get("content")
    if isinstance(conteudo, str):
        return conteudo
    return _texto_do_retorno({"content": conteudo if isinstance(conteudo, list) else []})


def _briefing_do_transcript(caminho) -> str:
    """Primeira mensagem de usuário do JSONL do subagente: é o briefing que ele recebeu."""
    if not isinstance(caminho, str) or not caminho:
        return ""
    try:
        with open(os.path.expanduser(caminho), encoding="utf-8") as fh:
            for linha in itertools.islice(fh, LINHAS_ATE_O_BRIEFING):
                texto = _texto_de_usuario(linha)
                if texto:
                    return texto
    except (OSError, UnicodeDecodeError):
        return ""
    return ""


def _entrada_estruturada(linha: str):
    """`input` do `StructuredOutput` numa linha do transcript; None se a linha não o traz."""
    try:
        registro = json.loads(linha)
    except ValueError:
        return None
    mensagem = registro.get("message") if isinstance(registro, dict) else None
    conteudo = mensagem.get("content") if isinstance(mensagem, dict) else None
    for bloco in reversed(conteudo) if isinstance(conteudo, list) else []:
        if (isinstance(bloco, dict) and bloco.get("type") == "tool_use"
                and bloco.get("name") == NOME_SAIDA_ESTRUTURADA
                and isinstance(bloco.get("input"), dict)):
            return bloco["input"]
    return None


def _saida_estruturada(caminho) -> str:
    """Agente de workflow (roda com `schema`) entrega o contrato chamando `StructuredOutput`,
    não em texto. Devolve o ÚLTIMO `input` dele como JSON, para o parser de texto de sempre
    reconhecer; "" sem transcript, ilegível ou sem a chamada."""
    if not isinstance(caminho, str) or not caminho:
        return ""
    try:
        with open(os.path.expanduser(caminho), encoding="utf-8") as fh:
            linhas = fh.readlines()
    except (OSError, UnicodeDecodeError):
        return ""
    for linha in reversed(linhas):
        entrada = _entrada_estruturada(linha)
        if entrada is not None:
            return json.dumps(entrada, ensure_ascii=False)
    return ""


def _texto_fallback(briefing: str):
    """O `dev` não seguiu o contrato JSON. Só nome de arquivo renderizável no briefing —
    nada de palavra genérica, que transformaria o lembrete em ruído.
    Devolve (texto, arquivos); (None, []) quando não há o que validar."""
    if not briefing.strip():
        return None, []

    por_nome = {}
    for caminho in RE_ARQ_RENDERIZAVEL.findall(briefing):
        if _descartavel(caminho):
            continue
        nome = caminho.rsplit("/", 1)[-1]
        if nome not in por_nome or len(caminho) < len(por_nome[nome]):
            por_nome[nome] = caminho
    achados = sorted(por_nome.values(), key=lambda c: (c.count("/"), c))
    if not achados:
        return None, []

    return (
        "[validação pendente — modo browser, decisão por FALLBACK] O retorno do `dev` não "
        "veio no contrato JSON esperado, então a decisão saiu do briefing de entrada: ele "
        f"menciona arquivo renderizável ({_resumo_lista(achados)}). Invoque o `tester` em "
        "modo browser ANTES de marcar a tarefa como concluída em tasks.md, e peça ao `dev` os "
        "`comandos_para_subir` (ou descubra-os) — este hook não os recebeu. " + BLOQUEIO +
        "\n" + AVISO
    ), achados


# --- retorno do dev: classificação -------------------------------------------------------

def _motivo_contrato(renderizaveis: list, externos: list) -> str:
    if renderizaveis:
        # Renderizável sem comando para subir: ainda é superfície, mas o print não se sustenta.
        return ("alterou arquivo de interface sem devolver comando para subir "
                f"({_resumo_lista(renderizaveis, 3)})")
    if externos:
        return f"alterou superfície externa verificável ({_resumo_lista(externos, 3)})"
    return "devolveu comando para subir a aplicação"


def _classificar_dev(retorno: dict):
    """`Decisao` da validação que o retorno do `dev` exige; None se nenhuma."""
    arquivos = _lista_de_strings(retorno.get("arquivos_alterados"))
    comandos = _lista_de_strings(retorno.get("comandos_para_subir"))
    relevantes = [a for a in arquivos if not _descartavel(a)]
    renderizaveis = [a for a in relevantes if _renderizavel(a)]
    externos = [a for a in relevantes if _superficie_externa(a)]
    resumo = _corte(retorno.get("resumo") or "sem resumo", 100)

    if renderizaveis and comandos:
        return Decisao("browser", _texto_browser(arquivos, comandos, renderizaveis),
                       arquivos, resumo)
    if renderizaveis or externos or (comandos and relevantes):
        texto = _texto_contrato(arquivos, comandos, _motivo_contrato(renderizaveis, externos))
        return Decisao("contrato", texto, arquivos, resumo)
    return None  # refactor, teste, doc, config de build ou tipo: nada a validar


def _decidir_dev(retorno, ler_briefing):
    """`ler_briefing` só é chamado no fallback: no SubagentStop ele lê o transcript."""
    if not isinstance(retorno, dict):
        texto, achados = _texto_fallback(ler_briefing())
        if texto is None:
            return None
        return Decisao("browser", texto, achados, "retorno fora do contrato (fallback)")
    if str(retorno.get("status") or "").strip().upper() == "BLOQUEADO":
        return None  # não há entrega para validar
    return _classificar_dev(retorno)


def _agent_id_da_resposta(resp: dict) -> str:
    agent_id = resp.get("agentId")
    return agent_id if isinstance(agent_id, str) else ""


def _tratar_dev(inp: dict, resp: dict, pasta: pathlib.Path) -> int:
    retorno = _retorno_do_dev(_texto_do_retorno(resp))
    decisao = _decidir_dev(retorno, lambda: _briefing_da_entrada(inp))
    # entrega nova: um PASSOU anterior não a cobre
    _registrar_dev(pasta, _agent_id_da_resposta(resp), retorno, decisao)
    return _emitir(decisao.texto) if decisao else 0


# --- retorno do tester: veredito ---------------------------------------------------------

def _retorno_do_tester(texto: str):
    """Primeiro objeto com `veredito` reconhecível; None se o `tester` não seguiu o contrato."""
    for bruto in _candidatos(texto):
        try:
            obj = json.loads(bruto)
        except Exception:
            continue
        if isinstance(obj, dict) and str(obj.get("veredito") or "").strip().upper() in VEREDITOS:
            return obj
    return None


def _corte(valor, limite: int = 240) -> str:
    texto = " ".join(str(valor or "").split())
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


def _resumo_falhas(retorno: dict) -> str:
    falhas = retorno.get("falhas")
    itens = []
    for f in falhas[:3] if isinstance(falhas, list) else []:
        if isinstance(f, dict):
            itens.append(f"[{_corte(f.get('tipo'), 20)}] {_corte(f.get('onde'), 60)}: "
                         f"{_corte(f.get('descricao'))}")
    return "\n".join(f"  - {i}" for i in itens)


def _texto_falhou(retorno: dict) -> str:
    return (
        "[validação FALHOU] O `tester` reprovou a entrega: ela NÃO está aprovada e a pendência "
        "continua. Devolva ao `dev` com a `recomendacao_para_dev` e invoque o `tester` de novo "
        "depois da correção — não marque a tarefa como concluída.\n"
        f"{_resumo_falhas(retorno)}\n"
        f"recomendacao_para_dev: {_corte(retorno.get('recomendacao_para_dev'))}"
    )


def _texto_bloqueado(retorno: dict) -> str:
    bloqueio = retorno.get("bloqueio") if isinstance(retorno.get("bloqueio"), dict) else {}
    return (
        "[validação BLOQUEADA] O `tester` NÃO conseguiu validar (ambiente ou teto de turnos, sem defeito "
        "achado) — isso não é aprovação e também não prova defeito. A entrega continua NÃO aprovada: resolva "
        "o ambiente (navegador, credencial, serviço, dependência) e invoque o `tester` de "
        "novo, ou pergunte ao usuário. Nunca siga adiante nem marque a tarefa como concluída "
        "com este veredito.\n"
        f"o que impediu: {_corte(bloqueio.get('o_que_impediu') or _resumo_falhas(retorno))}\n"
        f"o que destravaria: {_corte(bloqueio.get('o_que_destravaria'))}"
    )


TEXTO_SEM_VEREDITO = (
    "[validação pendente] O retorno do `tester` não trouxe um `veredito` legível "
    "(PASSOU | FALHOU | BLOQUEADO). Sem veredito não há aprovação: peça o JSON de retorno "
    "ou invoque o `tester` de novo antes de marcar a tarefa como concluída."
)


def _tratar_tester(inp: dict, resp: dict, pasta: pathlib.Path) -> int:
    _limpar_tester_em_andamento(pasta)
    retorno = _retorno_do_tester(_texto_do_retorno(resp))
    havia_pendencia = _registrar_veredito(pasta, _agent_id_da_resposta(resp), retorno,
                                          lambda: _briefing_da_entrada(inp))
    if retorno is None:
        return _emitir(TEXTO_SEM_VEREDITO) if havia_pendencia else 0
    veredito = str(retorno.get("veredito")).strip().upper()
    if veredito == "PASSOU":
        return 0  # só aprova o que veio ANTES dele: dev novo reabre
    return _emitir(_texto_falhou(retorno) if veredito == "FALHOU" else _texto_bloqueado(retorno))


def _papel_do_agente(subagent_type) -> str:
    """`dev`/`tester` puros ou com o namespace do plugin (`forge:dev`). Outro namespace => ''."""
    if not isinstance(subagent_type, str):
        return ""
    namespace, _, papel = subagent_type.rpartition(":")
    return papel if namespace in ("", "forge") else ""


# --- SubagentStop: qualquer profundidade, nunca imprime ----------------------------------

def _tratar_subagent_stop(d: dict) -> int:
    papel = _papel_do_agente(d.get("agent_type"))
    if papel not in ("dev", "tester"):
        return 0
    agent_id = d.get("agent_id") if isinstance(d.get("agent_id"), str) else ""
    mensagem = d.get("last_assistant_message")
    mensagem = mensagem if isinstance(mensagem, str) else ""
    pasta = _diretorio_de_estado(d.get("session_id"))

    def ler_briefing() -> str:
        return _briefing_do_transcript(d.get("agent_transcript_path"))

    def saida_estruturada() -> str:
        return _saida_estruturada(d.get("agent_transcript_path"))

    if papel == "dev":
        retorno = _retorno_do_dev(mensagem) or _retorno_do_dev(saida_estruturada())
        _registrar_dev(pasta, agent_id, retorno, _decidir_dev(retorno, ler_briefing))
    else:
        _limpar_tester_em_andamento(pasta)
        retorno = _retorno_do_tester(mensagem) or _retorno_do_tester(saida_estruturada())
        _registrar_veredito(pasta, agent_id, retorno, ler_briefing)
    return 0  # qualquer saída aqui manteria o SUBAGENTE rodando, não falaria com a raiz


# --- Stop: a raiz não encerra o turno com entrega sem tester -----------------------------

def _razao_do_bloqueio(entregas: list, ultimo_veredito) -> str:
    linhas = [f"  - modo {e.get('modo')}: {_resumo_lista(e.get('arquivos') or [], 3)} "
              f"({e.get('resumo')})" for e in entregas[:5]]
    veredito = ""
    if ultimo_veredito:
        veredito = (f"\nÚltimo tester: {ultimo_veredito.get('veredito')} — "
                    f"{ultimo_veredito.get('resumo')}")
    return (
        "[Forge] Entrega de `dev` sem validação do `tester`:\n" + "\n".join(linhas) + veredito
        + "\nDespache o `forge:tester` no modo indicado (com os arquivos e os "
        "comandos_para_subir do `dev`) ou explique ao usuário por que esta entrega não "
        "precisa de validação. Não a dê como concluída antes."
    )


def _tratar_stop(d: dict) -> int:
    if d.get("agent_id") or d.get("stop_hook_active"):
        return 0  # `stop_hook_active`: já continuamos uma vez por causa de Stop; nunca em laço
    pasta = _diretorio_de_estado(d.get("session_id"))
    if not (pasta / ARQUIVO_PENDENTE).is_file():
        return 0
    if _tester_marcado(pasta) or _subagente_do_forge_em_voo(d.get("background_tasks")):
        return 0
    with _estado_travado(pasta) as estado:
        novas = [e for e in estado.entregas if not e.get("cobrado")]
        for entrega in novas:
            entrega["cobrado"] = True
        ultimo_veredito = estado.ultimo_veredito
    if not novas:
        return 0
    print(json.dumps({"decision": "block", "reason": _razao_do_bloqueio(novas, ultimo_veredito)},
                     ensure_ascii=False))
    return 0


# --- PostToolUse(Agent): lançamento assíncrono e término síncrono (CLIs antigas) ---------

def _tratar_post_tool_use(d: dict) -> int:
    # Só a sessão-raiz orquestra; um subagente que despache outro não é o nosso caso.
    if d.get("agent_id"):
        return 0
    inp = d.get("tool_input")
    if not isinstance(inp, dict):
        return 0
    tipo = _papel_do_agente(inp.get("subagent_type"))
    resp = d.get("tool_response")
    if tipo not in ("dev", "tester") or not isinstance(resp, dict):
        return 0
    pasta = _diretorio_de_estado(d.get("session_id"))
    status = resp.get("status") or ""
    if status == "async_launched":
        if tipo == "tester":
            _marcar_tester_em_andamento(pasta)
        return 0  # o retorno chega no SubagentStop
    if status != "completed":
        return 0  # erro ou cancelado: não há entrega nem veredito para classificar
    if tipo == "tester":
        return _tratar_tester(inp, resp, pasta)
    return _tratar_dev(inp, resp, pasta)


# --- entrada -----------------------------------------------------------------------------

TRATADORES = {"SubagentStop": _tratar_subagent_stop, "Stop": _tratar_stop}


def main() -> int:
    try:
        d = json.load(sys.stdin)
    except Exception:
        return 0  # payload ilegível nunca atrapalha o trabalho
    if not isinstance(d, dict):
        return 0
    evento = d.get("hook_event_name")
    tratador = TRATADORES.get(evento if isinstance(evento, str) else "", _tratar_post_tool_use)
    return tratador(d)


if __name__ == "__main__":
    sys.exit(main())
