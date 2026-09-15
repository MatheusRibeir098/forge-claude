#!/usr/bin/env python3
"""PostToolUse (Agent): ao fim de cada `dev`, decide se a tarefa precisa do `tester` e em que
modo — e injeta isso no orquestrador com os dados prontos, para ele não reler nada.

O QUE MUDOU, E POR QUE A DECISÃO PASSOU A SER PELO RETORNO
A versão anterior decidia pelo BRIEFING (`tool_input`), apoiada em três fatos da CLI 2.1.260:
lançamento assíncrono (`tool_response` = {"isAsync": true, "status": "async_launched"}),
`additionalContext` do SubagentStop não injetado, e SubagentStop disparando 9× por invocação.
Os dois primeiros CADUCARAM. Verificado com payload real na CLI 2.1.272:
  1. `tool_response.status` vem "completed" e o hook dispara no TÉRMINO, com o retorno
     completo do subagente — não mais no lançamento.
  2. O retorno do `dev` está em `tool_response.content[0].text`, tipicamente dentro de uma
     cerca ```json (o `dev` costuma escrever texto solto em volta; por isso o parser abaixo
     tolera cerca e prosa).
  3. `tool_response` traz ainda `agentType`, `resolvedModel`, `totalTokens`,
     `totalToolUseCount` e `totalDurationMs` — dá para auditar a invocação aqui.
  4. Os lançamentos do Forge são síncronos: 350 de 355 sem `run_in_background`. O caso
     assíncrono sobra como `status` != "completed", e aí ficamos calados.
Fixtures reais em `tests/fixtures/`.

POR QUE ISSO IMPORTA — o custo do palpite pela entrada
Medição nos transcripts: dos 87 lembretes emitidos pela versão antiga, 44 vieram da lista de
palavras genéricas (`dashboard`, `layout`, `tela`, `botão`, `rota`…) em projetos sem UI
nenhuma (um MCP server e um compilador de YAML), e o regex de "API" casava
`packages/mcp-server/src/adapters/quicksight.ts` só porque a string contém "server". O
lembrete virou ruído e passou a ser ignorado TAMBÉM quando era legítimo: adesão de 100% para
0%. Um lembrete que mente é pior que nenhum.

Agora só existe um sinal e ele é factual: a lista `arquivos_alterados` que o próprio `dev`
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
de arquivo com extensão renderizável, sem a lista de palavras genéricas que causou o ruído. O
texto injetado avisa que foi fallback.

Saída silenciosa (exit 0) em qualquer payload ilegível: um hook nunca atrapalha o trabalho.
Só a sessão-raiz orquestra, daí a guarda `agent_id`.
"""
import json
import re
import sys

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


def _emitir_browser(arquivos: list, comandos: list, renderizaveis: list) -> int:
    return _emitir(
        "[validação pendente — modo browser] O `dev` terminou e alterou arquivo renderizável "
        f"({_resumo_lista(renderizaveis, 3)}) com comando para subir. Invoque o `tester` em "
        "modo browser ANTES de marcar a tarefa como concluída em tasks.md: ele sobe a "
        "aplicação, navega e tira print (teto explícito de 5). " + BLOQUEIO + "\n"
        f"arquivos_alterados: {_resumo_lista(arquivos)}\n"
        f"{_bloco_comandos(comandos)}\n" + AVISO
    )


def _emitir_contrato(arquivos: list, comandos: list, motivo: str) -> int:
    return _emitir(
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


def _fallback(inp: dict) -> int:
    """O `dev` não seguiu o contrato JSON. Só nome de arquivo renderizável no briefing —
    nada de palavra genérica, que foi o que transformou o lembrete em ruído."""
    briefing = " ".join(str(inp.get(k) or "") for k in ("prompt", "description"))
    if not briefing.strip():
        return 0

    por_nome = {}
    for caminho in RE_ARQ_RENDERIZAVEL.findall(briefing):
        if _descartavel(caminho):
            continue
        nome = caminho.rsplit("/", 1)[-1]
        if nome not in por_nome or len(caminho) < len(por_nome[nome]):
            por_nome[nome] = caminho
    achados = sorted(por_nome.values(), key=lambda c: (c.count("/"), c))
    if not achados:
        return 0

    return _emitir(
        "[validação pendente — modo browser, decisão por FALLBACK] O retorno do `dev` não "
        "veio no contrato JSON esperado, então a decisão saiu do briefing de entrada: ele "
        f"menciona arquivo renderizável ({_resumo_lista(achados)}). Invoque o `tester` em "
        "modo browser ANTES de marcar a tarefa como concluída em tasks.md, e peça ao `dev` os "
        "`comandos_para_subir` (ou descubra-os) — este hook não os recebeu. " + BLOQUEIO +
        "\n" + AVISO
    )


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
    if not isinstance(inp, dict) or (inp.get("subagent_type") or "") != "dev":
        return 0

    resp = d.get("tool_response")
    if not isinstance(resp, dict):
        return 0
    # 2.1.272: "completed" é o término síncrono com retorno. Qualquer outro estado
    # (async_launched, error, cancelado) não tem entrega para classificar.
    if (resp.get("status") or "") != "completed":
        return 0

    retorno = _retorno_do_dev(_texto_do_retorno(resp))
    if not isinstance(retorno, dict):
        return _fallback(inp)

    if str(retorno.get("status") or "").strip().upper() == "BLOQUEADO":
        return 0  # não há entrega para validar

    arquivos = _lista_de_strings(retorno.get("arquivos_alterados"))
    comandos = _lista_de_strings(retorno.get("comandos_para_subir"))
    relevantes = [a for a in arquivos if not _descartavel(a)]
    renderizaveis = [a for a in relevantes if _renderizavel(a)]

    if renderizaveis and comandos:
        return _emitir_browser(arquivos, comandos, renderizaveis)

    if renderizaveis:
        # Renderizável sem comando para subir: ainda é superfície, mas o print não se sustenta.
        return _emitir_contrato(
            arquivos, comandos,
            "alterou arquivo de interface sem devolver comando para subir "
            f"({_resumo_lista(renderizaveis, 3)})")

    externos = [a for a in relevantes if _superficie_externa(a)]
    if externos:
        return _emitir_contrato(
            arquivos, comandos,
            f"alterou superfície externa verificável ({_resumo_lista(externos, 3)})")

    if comandos and relevantes:
        return _emitir_contrato(
            arquivos, comandos,
            "devolveu comando para subir a aplicação")

    return 0  # refactor, teste, doc, config de build ou tipo: nada a validar


if __name__ == "__main__":
    sys.exit(main())
