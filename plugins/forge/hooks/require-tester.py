#!/usr/bin/env python3
"""PostToolUse (Agent): ao fim de cada `dev`, decide se a tarefa precisa do `tester` e em que
modo — e injeta isso no orquestrador com os dados prontos, para ele não reler nada.

POR QUE A DECISÃO É PELO RETORNO DO `dev`, E NÃO PELO BRIEFING
Decidir pelo BRIEFING (`tool_input`) exigiria disparar no lançamento do subagente, antes de
existir entrega, e dependeria de o lançamento ser assíncrono
(`tool_response` = {"isAsync": true, "status": "async_launched"}). Na CLI 2.1.272 o hook
dispara no término, com o retorno completo. Compatibilidade, verificada na CLI 2.1.272 com
payloads capturados:
  1. `tool_response.status` vem "completed" e o hook dispara no TÉRMINO, com o retorno
     completo do subagente, e não no lançamento.
  2. O retorno do `dev` está em `tool_response.content[0].text`, tipicamente dentro de uma
     cerca ```json (o `dev` costuma escrever texto solto em volta; por isso o parser abaixo
     tolera cerca e prosa).
  3. `tool_response` traz ainda `agentType`, `resolvedModel`, `totalTokens`,
     `totalToolUseCount` e `totalDurationMs` — dá para auditar a invocação aqui.
  4. O Forge lança subagentes de forma síncrona (sem `run_in_background`). O caso
     assíncrono aparece como `status` != "completed", e aí ficamos calados.
Fixtures capturadas em `tests/fixtures/`.

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
O hook também roda no retorno do `tester` e guarda uma pendência por sessão (ver "estado"):
  - retorno do `dev` que exige validação -> marca a pendência (reabre, mesmo após um PASSOU);
  - `tester` PASSOU    -> limpa a pendência (só cobre o que veio ANTES dele);
  - `tester` FALHOU    -> mantém a pendência e lembra: devolver ao `dev` e revalidar;
  - `tester` BLOQUEADO -> mantém a pendência e lembra: NÃO é aprovação; resolver o ambiente
                          ou perguntar ao usuário, nunca seguir adiante.
Entrega de `dev` só fica aprovada por um PASSOU posterior ao ÚLTIMO retorno de `dev`.

Saída silenciosa (exit 0) em qualquer payload ilegível: um hook nunca atrapalha o trabalho.
Só a sessão-raiz orquestra, daí a guarda `agent_id`.
"""
import json
import os
import pathlib
import re
import sys
import time

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


# --- estado: a pendência de validação, por sessão -----------------------------------------
# Mesmo esquema do `delega-varredura.py` e do `subagent-turn-budget.sh`: `FORGE_STATE_DIR`
# explícito > `XDG_RUNTIME_DIR` > `TMPDIR` > `/tmp`, sob `forge/validacao/<session_id>`.
# Um arquivo `pendente` existe enquanto houver entrega de `dev` sem PASSOU do `tester` DEPOIS
# dela. Os eventos chegam em ordem, então o arquivo basta: `dev` o cria, PASSOU o remove.

RE_SESSAO_INVALIDA = re.compile(r"[^A-Za-z0-9_-]")
ARQUIVO_PENDENTE = "pendente"
IDADE_MAXIMA_S = 24 * 3600
VEREDITOS = ("PASSOU", "FALHOU", "BLOQUEADO")


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
            if item.is_file() and item.stat().st_mtime < limite:
                item.unlink()
        except OSError:
            continue


def _marcar_pendente(estado: pathlib.Path, arquivos: list) -> None:
    """Falha de escrita nunca atrapalha: sem estado o hook só perde a memória."""
    try:
        estado.mkdir(parents=True, exist_ok=True)
        _limpar_antigos(estado)
        (estado / ARQUIVO_PENDENTE).write_text(
            json.dumps({"arquivos": arquivos[:20]}, ensure_ascii=False))
    except OSError:
        return


def _limpar_pendente(estado: pathlib.Path) -> None:
    try:
        (estado / ARQUIVO_PENDENTE).unlink()
    except OSError:
        return


def _ha_pendente(estado: pathlib.Path) -> bool:
    return (estado / ARQUIVO_PENDENTE).is_file()


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


def _texto_fallback(inp: dict):
    """O `dev` não seguiu o contrato JSON. Só nome de arquivo renderizável no briefing —
    nada de palavra genérica, que transformaria o lembrete em ruído.
    Devolve (texto, arquivos); (None, []) quando não há o que validar."""
    briefing = " ".join(str(inp.get(k) or "") for k in ("prompt", "description"))
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

def _classificar_dev(retorno: dict):
    """(texto, arquivos) da validação que o retorno do `dev` exige; (None, []) se nenhuma."""
    arquivos = _lista_de_strings(retorno.get("arquivos_alterados"))
    comandos = _lista_de_strings(retorno.get("comandos_para_subir"))
    relevantes = [a for a in arquivos if not _descartavel(a)]
    renderizaveis = [a for a in relevantes if _renderizavel(a)]
    externos = [a for a in relevantes if _superficie_externa(a)]

    if renderizaveis and comandos:
        return _texto_browser(arquivos, comandos, renderizaveis), arquivos
    if renderizaveis:
        # Renderizável sem comando para subir: ainda é superfície, mas o print não se sustenta.
        return _texto_contrato(
            arquivos, comandos,
            "alterou arquivo de interface sem devolver comando para subir "
            f"({_resumo_lista(renderizaveis, 3)})"), arquivos
    if externos:
        return _texto_contrato(
            arquivos, comandos,
            f"alterou superfície externa verificável ({_resumo_lista(externos, 3)})"), arquivos
    if comandos and relevantes:
        return _texto_contrato(
            arquivos, comandos, "devolveu comando para subir a aplicação"), arquivos
    return None, []  # refactor, teste, doc, config de build ou tipo: nada a validar


def _tratar_dev(inp: dict, resp: dict, estado: pathlib.Path) -> int:
    retorno = _retorno_do_dev(_texto_do_retorno(resp))
    if not isinstance(retorno, dict):
        texto, arquivos = _texto_fallback(inp)
    elif str(retorno.get("status") or "").strip().upper() == "BLOQUEADO":
        return 0  # não há entrega para validar
    else:
        texto, arquivos = _classificar_dev(retorno)
    if texto is None:
        return 0
    _marcar_pendente(estado, arquivos)  # entrega nova: um PASSOU anterior não a cobre
    return _emitir(texto)


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


def _tratar_tester(resp: dict, estado: pathlib.Path) -> int:
    retorno = _retorno_do_tester(_texto_do_retorno(resp))
    if retorno is None:
        return _emitir(TEXTO_SEM_VEREDITO) if _ha_pendente(estado) else 0
    veredito = str(retorno.get("veredito")).strip().upper()
    if veredito == "PASSOU":
        _limpar_pendente(estado)  # só aprova o que veio ANTES dele: dev novo reabre
        return 0
    return _emitir(_texto_falhou(retorno) if veredito == "FALHOU" else _texto_bloqueado(retorno))


def _papel_do_agente(subagent_type) -> str:
    """`dev`/`tester` puros ou com o namespace do plugin (`forge:dev`). Outro namespace => ''."""
    if not isinstance(subagent_type, str):
        return ""
    namespace, _, papel = subagent_type.rpartition(":")
    return papel if namespace in ("", "forge") else ""


# --- entrada -----------------------------------------------------------------------------

def main() -> int:
    try:
        d = json.load(sys.stdin)
    except Exception:
        return 0  # payload ilegível nunca atrapalha o trabalho
    if not isinstance(d, dict):
        return 0

    # Só a sessão-raiz orquestra; um subagente que despache outro não é o nosso caso.
    if d.get("agent_id"):
        return 0

    inp = d.get("tool_input")
    if not isinstance(inp, dict):
        return 0
    tipo = _papel_do_agente(inp.get("subagent_type"))
    if tipo not in ("dev", "tester"):
        return 0

    resp = d.get("tool_response")
    if not isinstance(resp, dict):
        return 0
    # 2.1.272: "completed" é o término síncrono com retorno. Qualquer outro estado
    # (async_launched, error, cancelado) não tem entrega nem veredito para classificar.
    if (resp.get("status") or "") != "completed":
        return 0

    estado = _diretorio_de_estado(d.get("session_id"))
    if tipo == "tester":
        return _tratar_tester(resp, estado)
    return _tratar_dev(inp, resp, estado)


if __name__ == "__main__":
    sys.exit(main())
