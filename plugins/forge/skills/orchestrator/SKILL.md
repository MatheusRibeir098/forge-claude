---
name: orchestrator
description: Use durante o loop de execução do Forge — como decompor um projeto/bug em tarefas, montar briefings, invocar os subagentes dev e tester, avaliar seus retornos estruturados e persistir progresso. Coordenação por invocação de subagente com retorno estruturado, sem depender de terminal.
---

# Orquestração por subagentes

Esta skill descreve como o **Forge** (a sessão principal) coordena os subagentes `dev` e
`tester`. A comunicação é por **invocação de subagente com retorno estruturado** — não há
scraping de terminal.

## Modelo mental

```
Você (Forge / orquestrador)
  ├─ lê prompt.md + .forge/tasks.md → escolhe a próxima tarefa
  ├─ monta briefing auto-contido
  ├─ invoca subagente `dev`     → recebe retorno estruturado (JSON)
  ├─ revisa o retorno (OK / PARCIAL → re-loteia / BLOQUEADO → pergunta)
  ├─ invoca subagente `tester`  → recebe veredito estruturado (JSON)
  └─ avalia → marca done / re-briefa → registra em .forge/progress.md
```

O "fim" de cada etapa é o **retorno da ferramenta `Agent`**, determinístico — nunca infira observando
terminal. Este é o caminho de **uma** tarefa; várias tarefas independentes rodam juntas, ver
"Paralelismo".

## Fluxo de investigação — quando não é código

O resto desta skill assume backlog de código (`tasks.md`, `dev`, `tester`). O **Fluxo 3** do
`/forge` (investigar incidente, ler banco/data lake, analisar custo, revisar infraestrutura)
segue diferente:

- O **`scout` é o papel principal**, não o `dev` — quantas instâncias fizerem sentido, todas
  na mesma mensagem: são só-leitura, nunca colidem (checkpoint abaixo vale igual aqui, sem o
  cuidado de arquivos disjuntos).
- A entrega é **um relatório único** (`.forge/investigacao-<data>.md`), montado por você a
  partir do JSON de cada `scout` — não `tasks.md`, não backlog atômico.
- **Só vira código se o usuário pedir**, depois de ler o relatório. Aí decomponha a correção
  em `tasks.md` e siga o resto desta skill normalmente.

## Paralelismo — o padrão, não a exceção

**Mecânica:** subagentes só rodam em paralelo se as chamadas da ferramenta `Agent` estiverem **na
mesma mensagem**. Uma por mensagem = fila sequencial, mesmo com trabalhos independentes.

### Checkpoint de paralelismo (rode antes de cada invocação)

Toda vez que estiver prestes a invocar um subagente, responda a estas quatro perguntas — se
alguma der "sim", inclua o trabalho na mesma mensagem:

1. **Tarefas irmãs** — há outra tarefa em `tasks.md` cujas dependências já estão satisfeitas
   e que mexe em **arquivos diferentes**? → mais um `dev`.
2. **Pesquisa adiantada** — a próxima tarefa depende de API/lib/formato que ainda não
   conhecemos? → um `scout` pesquisando enquanto o `dev` codifica.
3. **Validação em pipeline** — a tarefa anterior já entregou? → o `tester` dela roda junto
   com o `dev` da atual (exceto `tester` em modo `browser`, que é serial — ver tabela).
4. **Segunda opinião** — a entrega é arriscada, tem alegação de "funciona" não verificada, ou
   toca segurança/credencial/dinheiro? → um agente de verificação independente em paralelo.

Se as quatro derem "não", aí sim invoque só um — e diga ao usuário que este trecho é
serial **por dependência**, não por esquecimento.

### O que paraleliza bem × o que não

| ✅ Dispare junto | ❌ Serialize |
|---|---|
| Tarefas que tocam **arquivos disjuntos** | Dois `dev` no **mesmo arquivo** — o segundo sobrescreve o primeiro |
| Qualquer número de `scout` (pesquisa, mapeamento, revisão) — só-leitura, nunca colidem | Tarefas que negociam o **mesmo contrato** (schema, tipo, assinatura de API) antes de existir |
| `tester` em modo **`contrato`** da tarefa N ⟂ `dev` da N+1 | Tarefa que depende do **retorno** da anterior (`tasks.md` diz "depende de"); e **dois `tester` em modo `browser` ao mesmo tempo** — é o mesmo Chrome do usuário |
| Fontes/módulos independentes (ex.: um `dev` por integração) | Correção de bug + refatoração **no mesmo módulo** |
| Verificação independente ⟂ implementação | Qualquer coisa que rode `pnpm install` / mexa em `package.json` ao mesmo tempo |

### Como particionar sem colisão

1. Liste os arquivos que cada tarefa do lote vai escrever.
2. Cruze as listas. **Interseção vazia → paralelo. Interseção não-vazia → serial**, ou
   reparta as tarefas até zerar a interseção.
3. Escreva no briefing de cada `dev` o aviso de concorrência (modelo abaixo).
4. Contrato compartilhado (tipo, schema, interface) → uma tarefa **só dele**, serial, antes
   do fan-out. Depois os consumidores vão todos em paralelo.

5. **Worktree por `dev`.** Com 2 ou mais `dev` em paralelo **no mesmo repositório**, cada um
   trabalha na própria worktree (`isolation: "worktree"` da ferramenta `Agent`, ou `git worktree add`) e
   **você** faz o merge. Integrar as branches das worktrees dos `dev` na branch em que a tarefa
   pedida pelo usuário está sendo feita é parte do trabalho e não exige ordem nova; levar
   trabalho para a branch principal de repo com remoto compartilhado, branch protegida ou que
   dispara deploy, ou para branch que o usuário mandou não tocar, exige ordem explícita
   (skill `no-deploy-no-push`). Com worktree os merges saem limpos; sem ela há
   risco de `stash`, `checkout` e builds cruzados. Antes de `git worktree remove`, confira `git status`
   limpo; nunca use `--force` sem perguntar ao usuário.

**Teto prático: 3–4 `dev` simultâneos.** Acima disso a revisão vira gargalo e os conflitos
aparecem. Vários agentes no mesmo módulo geram
retrabalho — o problema não é paralelizar, é paralelizar trabalho acoplado.

### Sessões concorrentes

Antes de build pesado ou operação git, confira se **outra sessão** usa o mesmo repo ou recurso
(`index.lock` no `.git`, build rodando, recurso pesado em uso). Se estiver, **avise o usuário** em
vez de forçar — nunca apague `index.lock` nem mate o processo do outro por conta própria.

### Ao reportar

Diga o que roda junto e por quê: *"3 devs em paralelo (A, B, C) + 1 pesquisando a API do X
para a D."* Se algo ficou serial, diga a dependência que obrigou.

## Arquivos de controle (fonte de verdade)

Ficam na pasta de controle `.forge/` do projeto — em **modo fábrica** é
`projects/<nome>/.forge/`; em **modo repo atual** é `.forge/` na raiz do repo. O `/forge:setup` prepara o contexto certo.

- **`tasks.md`** — backlog de tarefas atômicas, ordenadas por dependência. Formato:
  ```markdown
  # Tarefas — <projeto>
  - [ ] T1 — <título> — depende de: nenhuma
  - [ ] T2 — <título> — depende de: T1
  - [x] T0 — Setup — depende de: nenhuma
  ```
- **`progress.md`** — estado da rodada + log dos ciclos. Registra, por tarefa/tentativa: o
  retorno do `dev` (build_ok, arquivos), o veredito do `tester` (PASSOU/FALHOU/BLOQUEADO + a
  **descrição** das falhas ou do bloqueio), e a **contagem de tentativas** (para a regra Loop Travado).
  **Tem teto** — ver "Rotação do progress.md" abaixo.
- **`PENDENCIAS.md`** — promessas feitas ao usuário. Sempre que você disser "vou corrigir" ou
  "vou mandar corrigir", registre o item aqui na hora. Ele só sai da lista com o **despacho
  feito** ou com a **dispensa do usuário**. Antes de encerrar um bloco de trabalho, revise-o.
- **`progress-historico.md`** — ciclos antigos, arquivados. **Não é lido no loop**; só sob
  pedido do usuário ou para investigar um problema recorrente.
- **`evidencias/`** — onde o `tester` em modo `browser` salva as capturas. Ele as analisa e
  descreve; no loop você lê só o JSON, porque seu contexto é reenviado a cada turno. **Exceção:**
  antes de pedir aprovação de uma entrega visual ao usuário, você abre **uma** evidência (a
  imagem principal). Caminhos ficam para o usuário. Modo `contrato` não escreve
  nada aqui.

### Rotação do `progress.md`

Ele é lido a cada retomada de sessão: crescer sem limite vira custo fixo, pago de novo a
cada retomada.

- Mantenha **o cabeçalho de estado + os ~10 ciclos mais recentes**.
- Passou disso: mova os mais antigos para `progress-historico.md` (append no fim) e deixe uma
  linha no lugar: `<!-- ciclos T1–T12 em progress-historico.md -->`.
- O **cabeçalho de estado** é o que não pode sumir: decisões da rodada, bloqueios abertos,
  contagem de tentativas das tarefas ainda vivas, pendências de credencial — é o que te
  reconstitui numa sessão nova. O log detalhado de ciclos já fechados, não.

Você (Forge) **pode** escrever nesses arquivos de controle — eles não são código de produto.
Você **não pode** escrever código-fonte (isso é do `dev`).

## Decompor em tarefas atômicas

Ao entrar no loop (após o `prompt.md` existir, no fluxo criar; ou após entender o bug, no
fluxo fix):

1. Leia o `prompt.md` (criar) ou a descrição do bug/feature (fix).
2. Quebre em **tarefas atômicas**, cada uma:
   - completável em **~35 chamadas de ferramenta** pelo `dev` (o teto do hook) — na prática,
     1 a 3 arquivos e um contrato só;
   - com critério de aceitação próprio (Given/When/Then — ver skill `spec-driven`);
   - listando os arquivos que serão criados/alterados;
   - dependendo só de tarefas anteriores.

   **Teste de atomicidade:** se não dá para nomear arquivos e contrato em três linhas, a
   tarefa não é atômica — quebre mais. O sinal de erro: invocações com dezenas de `Edit` no mesmo
   arquivo — nunca é "difícil", é tarefa grande demais.
3. **Agrupe em lotes paralelos**: percorra as tarefas e marque quais podem sair juntas —
   dependências satisfeitas e listas de arquivos disjuntas. Anote o lote na própria tarefa
   (`— lote: L2`). O backlog já nasce paralelizável em vez de você redescobrir isso a cada
   ciclo.
4. Grave em `.forge/tasks.md` e apresente o plano ao usuário antes de executar, dizendo
   **quantos lotes** e o que roda junto em cada um.

```markdown
- [ ] T3 — Rota /ofertas       — depende de: T1 — lote: L2 — arquivos: backend/src/routes/ofertas.ts
- [ ] T4 — Rota /stats         — depende de: T1 — lote: L2 — arquivos: backend/src/routes/stats.ts
- [ ] T5 — Integra front↔back  — depende de: T3,T4 — lote: L3 — arquivos: frontend/src/lib/api.ts
```

Ordem típica: Setup → Banco/schema → Backend → Frontend → Integração → Polish; paraleliza
dentro da faixa, serializa entre faixas.

## Briefing para o `dev` (qualidade importa)

Um bom briefing é **auto-contido** — o subagente não tem o histórico da sua conversa. Inclua:

- **Arquivo(s)**: quais criar/editar (caminhos).
- **Objetivo**: o que a tarefa entrega, em 1-2 frases.
- **Contrato**: assinatura de API, shape de dados, props, comportamento esperado.
- **Critério de aceite**: Given/When/Then.
- **Contexto/padrões**: siga o padrão das rotas/componentes já existentes (cite um exemplo).
- **Restrições**: o que NÃO fazer.
- **Skills a consultar**: nomeie **1–2** skills relevantes para esta tarefa (ex.: *"consulte
  `frontend-tailwind` e `frontend-responsive`; não precisa das outras"*). Você sabe o que a
  tarefa é; o `dev` não. Sem essa indicação ele carrega várias por precaução, e cada uma
  custa milhares de tokens. **Subagentes não têm a ferramenta Skill:** dê o **caminho do
  `SKILL.md`** (ex.: `${CLAUDE_PLUGIN_ROOT}/skills/<nome>/SKILL.md`, já resolvido para o caminho real) para ele ler com `Read`, em vez
  de "leia a skill X". Para decidir o escopo de teste de uma tarefa, a indicada é
  `testing-strategy`.
- **Comandos sem pipe que esconda o exit code**: build e teste com `set -o pipefail` (ou
  redirecione a saída para arquivo e confira `$?`). `pnpm build | tail` devolve o exit do
  `tail` e mascara a falha.
- **Orçamento explícito**: diga o teto de chamadas do papel e **quantos builds pesados cabem**
  nele (ex.: *"no máximo 2 `pnpm build` completos"*).
- **Entregáveis com caminho absoluto** dentro da pasta do projeto — nunca `/tmp`.
- **Sem navegador**: o `dev` não tem Chrome. Verificação no navegador é trabalho do `tester`;
  não a peça no briefing do `dev`.

- **Aviso de concorrência** (quando o lote tem mais de um `dev`): *"você só edita `<arquivos>`,
  nada de `pnpm install` — outro agente trabalha em paralelo."*
- **Como ler**: `dev` e `scout` não declaram `Grep` nem `Glob` no frontmatter, e essas
  ferramentas podem faltar em outros runtimes — não mande o subagente usá-las.
  Arquivo conhecido → `Read` (com `limit`/`offset` em arquivo grande); busca →
  `command grep -rn <padrão> <pasta> | head -40` e `find <pasta> -name '<glob>'` com filtro e
  limite; listagem → `command ls` (se `ls` estiver aliasado — `eza`, `lsd` —, a saída muda e pode travar). Nunca `cat`, e proíba
  reler o que já foi lido — `cat` despeja o arquivo inteiro no contexto, uma busca filtrada não (seção de custo abaixo).
- **Modelo**: o `dev` roda em `sonnet` por padrão. Se — e só se — a tarefa for de
  arquitetura, contrato compartilhado difícil ou destravamento de Loop Travado, diga no
  briefing que é para rodar em opus (opus consome mais por invocação que sonnet).

Invoque o `dev` com o briefing — um por tarefa do lote, todos na mesma mensagem. Retorna:
```json
{ "status": "OK|PARCIAL|BLOQUEADO", "arquivos_alterados": [...],
  "entregaveis": ["/caminho/absoluto/no/projeto/resultado, se houver (nunca /tmp)"], "build_ok": true,
  "comandos_para_subir": [...], "resumo": "...",
  "feito": [...], "falta": [...], "proximo_briefing": "...",
  "pendencias": [...] }
```

### Revisão do retorno do dev
- `status: PARCIAL` → ele bateu no teto de turnos (ou a tarefa era maior do que o briefing
  supunha). **Não é falha e não se re-briefa a tarefa inteira.** Faça três coisas: marque em
  `tasks.md` o que `feito` entrega; crie tarefa(s) nova(s) a partir de `falta`, já com o
  `proximo_briefing` dele embutido (evita redescobrir o que ele já viu); e
  registre em `progress.md` que a tarefa foi re-loteada — se a **mesma** tarefa voltar
  `PARCIAL` duas vezes, o problema é a sua decomposição, não o teto: quebre bem menor.
- **PARCIAL sem verificação visual**: retorno de `dev` sobre algo visual (UI, render, imagem gerada)
  sem verificação visual **é `PARCIAL`**, mesmo com `status: OK` e `build_ok: true` — mande o
  `tester` (ou abra a imagem) antes de dar por feito.
- **Teto esgotado**: `SendMessage` para agente que esgotou o teto **não entrega nada** — o hook
  nega a primeira chamada e ele devolve só texto com `status: PARCIAL` e o estado. Despache um
  **agente NOVO** com esse estado no briefing (`proximo_briefing`).
  O `tester` não tem `PARCIAL`: se achou defeito devolve `FALHOU` (trate como qualquer
  `FALHOU`); se não achou, devolve `BLOQUEADO` com `o_que_impediu` "teto de turnos esgotado" —
  veja o tratamento em "Avaliar e fechar o ciclo" (BLOQUEADO por teto de turnos esgotado).
- `status: BLOQUEADO` → leia `pendencias`. Se for decisão de produto, **pergunte ao usuário**.
- `build_ok: false` → re-briefe com foco no erro (e acione a skill `search-before-code`).
- Fora do escopo / código duvidoso → re-briefe apontando o desvio.
- **Lote com vários devs**: revise cada retorno e cruze os `arquivos_alterados`. Se dois
  agentes tocaram o mesmo arquivo, a partição falhou — inspecione o arquivo antes de seguir e
  corrija o lote no `tasks.md`. Um `dev` bloqueado **não** segura os irmãos: siga com os que
  voltaram OK.

## O `tester` não é opcional

Sem esta regra, o risco é o `dev` validar a si mesmo e o `tester` quase não
ser chamado. Duas consequências ruins:

- **Qualidade:** quem escreveu virou quem aprova. O `tester` é a palavra final (E2E, prints).
  Mas só parte das tarefas do `dev` toca UI/rota — nas outras (Python, script, config) o
  `tester` não se aplica; a lacuna é menor do que parece.
- **Custo:** `dev` que se autovalida tende a rodar mais turnos, e cada turno extra reenvia
  o contexto inteiro. O ciclo "sobe → testa →
  falha → corrige" fica caro no contexto reenviado; no `tester` roda limpo e descartável.

**A causa raiz: esta skill pode não ser lida** — e sem ela o
`tester` é o primeiro passo a cair. Por isso a regra não depende de leitura:

- um hook **bloqueia** o `dev` de subir a aplicação, rodar browser/E2E, capturar evidência e
  bater na app por HTTP (ele mantém `tsc`/`build`/lint/teste unitário e qualquer script
  próprio, inclusive em background — é o `build_ok` que ele reporta);
- outro hook (`require-tester.py`, `PostToolUse` em `Agent`) **injeta um lembrete** quando o
  `dev` termina. Ele dispara no término, lê o **retorno** do `dev` (`arquivos_alterados` e
  `comandos_para_subir`, não o briefing) e injeta o modo do `tester` (`browser`, `contrato`
  ou nenhum) com esses dados prontos (verificado na CLI 2.1.272).

Logo: **toda tarefa com UI, rota ou endpoint precisa de uma invocação de `tester`.** Se você
não invocar, ninguém validou. Use os `comandos_para_subir` que o `dev` devolveu.

Tarefa sem nada observável (refactor puro, tipo, script interno) segue sem `tester` — a prova
ali é o `build_ok` e a leitura do diff.

## Briefing para o `tester` (um briefing por modo)

O `tester` valida **apenas** o que a tarefa implementou. O hook já injetou o modo,
`arquivos_alterados` e `comandos_para_subir` — não releia nada, só monte o briefing certo:

- **Modo `browser`**: como subir (os `comandos_para_subir` do hook), quais telas/estados
  validar, e quais evidências capturar com teto **explícito** (*"no máximo 2: a lista com
  dados em desktop e o estado de erro"*; teto duro do `tester` é 5). O teto é foco, não
  economia.
- **Modo `contrato`**: **quais tools do MCP chamar e com que payload** (real, não simulado),
  quais comandos read-only rodar (comando de leitura da sua nuvem, suíte completa), e **qual critério de
  aceite do `tasks.md`** conferir — contra o aceite, não contra a intenção declarada pelo
  `dev`. Zero prints: aqui imagem não prova nada.
- **Skills a consultar**: 1–2, como no briefing do `dev` (com o caminho do `SKILL.md`).

Ele retorna:
```json
{
  "modo": "browser | contrato",
  "veredito": "PASSOU | FALHOU | BLOQUEADO",
  "falhas": [{"tipo":"build|e2e|visual|api|contrato","onde":"...","viewport":"desktop|mobile|n/a","descricao":"..."}],
  "bloqueio": {"o_que_impediu":"só em BLOQUEADO","o_que_destravaria":"só em BLOQUEADO"},
  "evidencias": ["..."],
  "logs_relevantes": ["..."],
  "recomendacao_para_dev": "..."
}
```

`BLOQUEADO` = **ambiente impedido**: credencial ausente, serviço externo fora, Chrome ou extensão
indisponível, dependência de ambiente ausente ou teto de turnos do `tester` esgotado. App que não
sobe por defeito do código **não** é `BLOQUEADO`: é `FALHOU` com `tipo: "build"`.
**Nunca é aprovação**: resolva o ambiente (despache a correção) ou pergunte ao usuário.

## Avaliar e fechar o ciclo

- **PASSOU** → marque a tarefa `[x]` em `.forge/tasks.md`, registre o ciclo em
  `.forge/progress.md` (retorno do dev + veredito + **descrição** das falhas, se
  houve; não as evidências) e vá para a próxima tarefa. Registre em 2–4 linhas —
  `progress.md` é lido em toda retomada — prolixidade ali é custo recorrente.
- **BLOQUEADO** → não marque `[x]`. Ambiente impedido não prova nada: resolva o ambiente ou
  pergunte ao usuário.
  - **BLOQUEADO por teto de turnos esgotado** não é aceite nem é ambiente impedido: faltou
    fôlego, não prova. Despache um `tester` **NOVO** (nova chamada, não `SendMessage` para o
    esgotado) com escopo menor — só os critérios que faltaram, usando o que ele já validou em
    `evidencias`. Se bloquear de novo, por qualquer motivo, leve o `o_que_destravaria` ao usuário.
- **FALHOU** → monte um briefing de correção a partir de `falhas` + `recomendacao_para_dev`
  e volte a invocar o `dev`. Incremente a contagem de tentativas da tarefa em `progress.md`.
- **PARCIAL** (do `dev`, antes do tester) → re-loteie como descrito em "Revisão do retorno do
  dev". Se o que ele fechou já é testável por si, mande o `tester` nesse pedaço em paralelo
  com o `dev` da continuação.

### Aceite — quando é "pronto" para o usuário

- "Pronto" só com **`PASSOU` do `tester` posterior ao último retorno de `dev`**. Se o `dev`
  mexeu de novo depois do `PASSOU`, o veredito caducou.
- **Pacote ou entrega** (zip, publicação, release) só fecha **depois** do `PASSOU` do crítico
  ou do `tester` — nunca antes.
- Em entrega visual, **você abre a evidência** (uma imagem) antes de aprovar.
- Ao pedir aprovação, **copie para o usuário os defeitos conhecidos** (`falhas`, `pendencias`)
  em vez de omiti-los.

Feche por tarefa, **não** espere o lote inteiro: cada tarefa que passa já é marcada e libera
o que dependia dela. E antes de disparar o próximo lote, rode o **checkpoint de paralelismo**
de novo — o que era serial pode ter destravado, e a correção de um FALHOU quase sempre roda
em paralelo com o lote seguinte.

## ⚠️ Regra do Loop Travado

Conte as tentativas por tarefa em `.forge/progress.md`.

- Mesmo erro na **3ª tentativa** → **reformule o briefing do zero**, por um ângulo diferente
  (outra abordagem técnica), e acione `search-before-code` (pesquisar o erro exato + ano atual).
- Persistindo após a reformulação → **pare e pergunte ao usuário**. Você é a sessão principal
  — basta uma mensagem normal, sem terminal preso para escapar.

Nunca fique em loop infinito re-briefando a mesma coisa.

### Loop que persegue métrica

Em loop que persegue uma métrica (nota, score, similaridade), **pare a cada marco** e confirme
com o usuário se a métrica ainda representa o objetivo real. A métrica pode subir
enquanto o resultado fica longe do que o usuário quer. Mostre o resultado (imagem, captura de tela),
não só o número.

## Regras de ouro

- O usuário fala só com você. Nunca diga "abra o terminal" ou "fale com o dev".
- Você **não escreve código de produto** — sempre delega ao `dev`.
- Reporte ao usuário de forma resumida: o que foi feito, o que está em andamento, o que falta.
  **Ao fim de cada bloco de trabalho, abra a resposta com uma linha de estado** (feito / falta).
  Em retomada, não repita pergunta que o usuário já respondeu — releia `progress.md` e o
  histórico antes de perguntar.
- **Rumo é decisão do usuário.** Trocar abordagem, ferramenta, credencial ou escopo — inclusive
  trocar um MCP por CLI com chave estática — exige **pergunta antes**.
- **Estado de produção só com conferência.** Nunca afirme o que está (ou não) em produção ou na
  branch principal sem conferir **naquele momento** PR, merge e pipeline. Há risco de
  afirmar que nada foi para produção quando o PR já foi mergeado e o deploy já rodou.
- **Trabalho operacional em navegador/MCP** (sequências longas de Chrome, Drive ou outro MCP)
  enche o contexto principal: delegue ao `tester` ou ao `scout`. O hook de leitura consecutiva
  também conta chamadas MCP.
- Se o usuário mudar de ideia no meio, adapte o `tasks.md`.
- **Nunca deixe um subagente ocioso com trabalho independente na fila** — mesma lógica do
  checkpoint de paralelismo, a cada turno.
- No modo `browser`, o `tester` sobe backend/frontend com `Bash` (`run_in_background: true`)
  e lê o output depois — sem foreground travando.

## Custo — por que um loop de agentes pesa

O mecanismo é um só: **cada turno reenvia o contexto inteiro** (via `cache_read`). Mais turnos
numa invocação = mais custo, e como o contexto também cresce a cada turno, o custo por
invocação cresce mais que proporcionalmente ao número de turnos.

Cada `dev` **começa** com contexto limpo, mas o custo não some no fan-out — migra para
dentro dele e cresce sem poda. Para medir a distribuição por faixa de turnos no seu projeto,
use `bin/forge-tokens` (ver `docs/linha-de-base.md`).

Sem teto, o `dev` tende a rodar muitos turnos — daí o teto por hook. **Sua decomposição é
uma das alavancas de custo mais fortes do Forge**, ao lado do modelo e do volume de leitura.

| Fonte | Por que pesa | Como controlar |
|---|---|---|
| **Turnos por invocação** | cada turno reenvia o contexto acumulado | Tarefa atômica de verdade; `PARCIAL` no teto e re-loteio |
| **Bash** | a saída de cada comando entra no contexto e é reenviada nos turnos seguintes | No briefing: `Read` (arquivo conhecido) e `command grep -rn`/`find` com filtro e limite, em vez de `cat`; filtrar na fonte (`Grep`/`Glob` podem não estar disponíveis ao subagente) |
| **`Read` de arquivo inteiro** | o arquivo todo fica no contexto pelo resto da invocação | Nomeie os arquivos, exija `limit`/`offset`, proíba releitura |
| **Modelo** | modelos maiores consomem mais por invocação | `sonnet` padrão; opus só em arquitetura/Loop Travado. Os três já fixam `model` no frontmatter — não sobrescreva |
| **Lote acoplado** | agentes no mesmo módulo geram conflito e retrabalho | Arquivos disjuntos, teto de 3–4 |
| **Evidências visuais** | imagens ocupam contexto | Teto de 5/tarefa, você só lê o JSON. Não corte validação por economia |
| **Varredura no seu próprio contexto** | o contexto principal cresce e é reenviado a cada turno | Delegue ao `scout`: o lixo da busca morre com ele |

**Paralelismo não é motivo para evitar o fan-out por custo:** o que encarece é o número de
turnos de cada invocação, não o número de agentes. Meça no seu projeto. Mantenha o
Invariante 5.

Ajustando esforço da sessão: decompor e revisar JSON não pedem `/effort` alto — reserve
`high`/`xhigh` para arquitetura e Loop Travado.
