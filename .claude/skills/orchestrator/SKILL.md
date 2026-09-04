---
name: orchestrator
description: Use durante o loop de execução do Forge — como decompor um projeto/bug em tarefas, montar briefings, invocar os subagentes dev e tester, avaliar seus retornos estruturados e persistir progresso. Substitui todo o mecanismo antigo de tmux.
---

# Orquestração por subagentes (sem tmux)

Esta skill descreve como o **Forge** (a sessão principal, que é o antigo "monitor")
coordena os subagentes `dev` e `tester`. A comunicação é por **invocação de subagente com
retorno estruturado** — não há tmux, send-keys, capture-pane, sleep ou scraping de terminal.

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

O "fim" de cada etapa é o **retorno da Task tool**, determinístico. Você nunca infere
conclusão observando um terminal.

O diagrama acima é o caminho de **uma** tarefa. Na prática você roda vários desses caminhos
ao mesmo tempo — ver "Paralelismo" logo abaixo.

## Paralelismo — o padrão, não a exceção

**Mecânica:** subagentes só rodam em paralelo se as chamadas da Task tool estiverem **na
mesma mensagem**. Uma chamada por mensagem = fila sequencial, mesmo que os trabalhos sejam
independentes. Então junte-as num bloco só.

### Checkpoint de paralelismo (rode antes de cada invocação)

Toda vez que estiver prestes a invocar um subagente, responda a estas quatro perguntas — se
alguma der "sim", inclua o trabalho na mesma mensagem:

1. **Tarefas irmãs** — há outra tarefa em `tasks.md` cujas dependências já estão satisfeitas
   e que mexe em **arquivos diferentes**? → mais um `dev`.
2. **Pesquisa adiantada** — a próxima tarefa depende de API/lib/formato que ainda não
   conhecemos? → um agente de leitura pesquisando enquanto o `dev` codifica.
3. **Validação em pipeline** — a tarefa anterior já entregou? → o `tester` dela roda junto
   com o `dev` da atual.
4. **Segunda opinião** — a entrega é arriscada, tem alegação de "funciona" não verificada, ou
   toca segurança/credencial/dinheiro? → um agente de verificação independente em paralelo
   (foi o que a tarefa A11-V do bot-ofertas pegou).

Se as quatro derem "não", aí sim invoque só um — e diga ao usuário que este trecho é
serial **por dependência**, não por esquecimento.

### O que paraleliza bem × o que não

| ✅ Dispare junto | ❌ Serialize |
|---|---|
| Tarefas que tocam **arquivos disjuntos** | Dois `dev` no **mesmo arquivo** — o segundo sobrescreve o primeiro |
| Qualquer número de agentes **só-leitura** (pesquisa, mapeamento, revisão) | Tarefas que negociam o **mesmo contrato** (schema, tipo compartilhado, assinatura de API) antes de ele existir |
| `tester` da tarefa N ⟂ `dev` da tarefa N+1 | Tarefa que depende do **retorno** da anterior (`tasks.md` diz "depende de") |
| Fontes/módulos independentes (ex.: um `dev` por integração) | Correção de bug + refatoração **no mesmo módulo** |
| Verificação independente ⟂ implementação | Qualquer coisa que rode `pnpm install` / mexa em `package.json` ao mesmo tempo |

### Como particionar sem colisão

1. Liste os arquivos que cada tarefa do lote vai escrever.
2. Cruze as listas. **Interseção vazia → paralelo. Interseção não-vazia → serial**, ou
   reparta as tarefas até zerar a interseção.
3. Escreva no briefing de cada `dev`: *"você é o único dono de `<arquivos>`; não edite nada
   fora dessa lista — outro agente está trabalhando em paralelo."*
4. Contrato compartilhado (tipo, schema, interface) → uma tarefa **só dele**, serial, antes
   do fan-out. Depois os consumidores vão todos em paralelo.

**Teto prático: 3–4 `dev` simultâneos.** Acima disso a revisão dos retornos vira o gargalo e
os conflitos aparecem. Lição registrada no `progress.md` do bot-ofertas: cinco agentes de uma
vez no mesmo módulo produziram retrabalho — o problema não foi o paralelismo, foi paralelizar
trabalho acoplado.

### Ao reportar

Diga o que está rodando junto e por quê: *"disparei 3 devs em paralelo (A, B, C — arquivos
disjuntos) + 1 pesquisando a API do X para a tarefa D."* Se algo ficou serial, diga a
dependência que obrigou.

## Arquivos de controle (fonte de verdade)

Ficam em `projects/<nome>/.forge/`:

- **`tasks.md`** — backlog de tarefas atômicas, ordenadas por dependência. Formato:
  ```markdown
  # Tarefas — <projeto>
  - [ ] T1 — <título> — depende de: nenhuma
  - [ ] T2 — <título> — depende de: T1
  - [x] T0 — Setup — depende de: nenhuma
  ```
- **`progress.md`** — estado da rodada + log dos ciclos. Registra, por tarefa/tentativa: o
  retorno do `dev` (build_ok, arquivos), o veredito do `tester` (PASSOU/FALHOU + a
  **descrição** das falhas), e a **contagem de tentativas** (para a regra Loop Travado).
  **Tem teto** — ver "Rotação do progress.md" abaixo.
- **`progress-historico.md`** — ciclos antigos, arquivados. **Não é lido no loop**; só sob
  pedido explícito do usuário ou quando você precisa investigar um problema recorrente.
- **`screenshots/`** — onde o `tester` salva as prints. Ele as analisa e descreve; **você não
  as abre** — não porque a imagem seja caríssima (medido: ~1% do loop), mas porque a análise
  visual é dele e o seu contexto é reenviado em todo turno da sessão. Os caminhos ficam para
  o usuário.

### Rotação do `progress.md`

O arquivo é lido a cada retomada de sessão, então crescimento sem limite vira custo fixo
crescente — um projeto de médio porte chega a milhares de tokens só nele.

- Mantenha **o cabeçalho de estado + os ~10 ciclos mais recentes**.
- Passou disso: mova os mais antigos para `progress-historico.md` (append no fim) e deixe uma
  linha no lugar: `<!-- ciclos T1–T12 em progress-historico.md -->`.
- O **cabeçalho de estado** é o que não pode sumir: decisões da rodada, bloqueios abertos,
  contagem de tentativas das tarefas ainda vivas, pendências de credencial. É ele que te
  reconstitui numa sessão nova — o log detalhado de ciclos já fechados, não.

Você (Forge) **pode** escrever nesses arquivos de controle — eles não são código de produto.
Você **não pode** escrever código-fonte (isso é do `dev`).

## Decompor em tarefas atômicas

Ao entrar no loop (após o `prompt.md` existir, no fluxo criar; ou após entender o bug, no
fluxo fix):

1. Leia o `prompt.md` (criar) ou a descrição do bug/feature (fix).
2. Quebre em **tarefas atômicas**, cada uma:
   - completável em **~26 chamadas de ferramenta** pelo `dev` (o teto do hook) — na prática,
     1 a 3 arquivos e um contrato só;
   - com critério de aceitação próprio (Given/When/Then — ver skill `spec-driven`);
   - listando os arquivos que serão criados/alterados;
   - dependendo só de tarefas anteriores.

   **Teste de atomicidade:** se você não consegue nomear os arquivos e o contrato em três
   linhas, a tarefa não é atômica — quebre mais. O sinal de que errou aparece depois no
   retorno: nos dados deste repo houve invocações com **38 `Edit` no mesmo arquivo**, o que
   nunca é "trabalho difícil", é sempre tarefa grande demais entregue como uma só.
3. **Agrupe em lotes paralelos**: percorra as tarefas e marque quais podem sair juntas —
   dependências satisfeitas e listas de arquivos disjuntas. Anote o lote na própria tarefa
   (`— lote: L2`). O backlog já nasce paralelizável em vez de você redescobrir isso a cada
   ciclo.
4. Grave em `.forge/tasks.md`. Apresente o plano ao usuário antes de começar a executar,
   dizendo **quantos lotes** e o que roda junto em cada um.

```markdown
- [ ] T3 — Rota /ofertas       — depende de: T1 — lote: L2 — arquivos: backend/src/routes/ofertas.ts
- [ ] T4 — Rota /stats         — depende de: T1 — lote: L2 — arquivos: backend/src/routes/stats.ts
- [ ] T5 — Integra front↔back  — depende de: T3,T4 — lote: L3 — arquivos: frontend/src/lib/api.ts
```

Ordem típica para projeto novo: Setup → Banco/schema → Backend (rotas/services) → Frontend
(páginas/componentes) → Integração front↔back → Polish (responsivo, dark mode, animações).
Dentro de cada faixa dessas, as peças costumam ser irmãs independentes — é aí que mora o
paralelismo fácil (uma rota por `dev`, uma página por `dev`). Entre faixas, há dependência
real: serialize.

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
  custa milhares de tokens no contexto dele.

- **Aviso de concorrência** (quando o lote tem mais de um `dev`): *"você é o único dono de
  `<arquivos>`; não edite nada fora dessa lista, nem rode `pnpm install` — outro agente está
  trabalhando em paralelo."*
- **Como ler**: mande usar `Grep`/`Glob`/`Read` (com `limit` em arquivo grande) em vez de
  `grep`/`find`/`cat` via Bash, e não reler o que já leu. Bash foi 61% de tudo que os
  subagentes ingeriram neste repo; `cat` custou em média 3,5× uma busca.
- **Modelo**: o `dev` roda em `sonnet` por padrão. Se — e só se — a tarefa for de
  arquitetura, contrato compartilhado difícil ou destravamento de Loop Travado, diga no
  briefing que é para rodar em opus (opus custou 2,8× por invocação nos dados medidos).

Invoque o subagente `dev` passando esse briefing — **um por tarefa do lote, todos na mesma
mensagem**. Cada um retorna:
```json
{ "status": "OK|PARCIAL|BLOQUEADO", "arquivos_alterados": [...], "build_ok": true,
  "comandos_para_subir": [...], "resumo": "...",
  "feito": [...], "falta": [...], "proximo_briefing": "...",
  "pendencias": [...] }
```

### Revisão do retorno do dev
- `status: PARCIAL` → ele bateu no teto de turnos (ou a tarefa era maior do que o briefing
  supunha). **Não é falha e não se re-briefa a tarefa inteira.** Faça três coisas: marque em
  `tasks.md` o que `feito` entrega; crie tarefa(s) nova(s) a partir de `falta`, já com o
  `proximo_briefing` dele embutido (é o que evita redescobrir o que ele já descobriu); e
  registre em `progress.md` que a tarefa foi re-loteada — se a **mesma** tarefa voltar
  `PARCIAL` duas vezes, o problema é a sua decomposição, não o teto: quebre bem menor.
- `status: BLOQUEADO` → leia `pendencias`. Se for decisão de produto, **pergunte ao usuário**.
- `build_ok: false` → re-briefe com foco no erro (e acione a skill `search-before-code`).
- Fora do escopo / código duvidoso → re-briefe apontando o desvio.
- **Lote com vários devs**: revise cada retorno e cruze os `arquivos_alterados`. Se dois
  agentes tocaram o mesmo arquivo, a partição falhou — inspecione o arquivo antes de seguir e
  corrija o lote no `tasks.md`. Um `dev` bloqueado **não** segura os irmãos: siga com os que
  voltaram OK.

## O `tester` não é opcional

Medido nos transcripts: **4 invocações de `tester` contra 180 de `dev`** — 78% dos `dev`
acabaram validando a si mesmos. Duas consequências, as duas ruins:

- **Qualidade:** quem escreveu o código virou quem aprova o código. O `tester` existe para ser
  a palavra final, com E2E e prints. A lacuna real é menor do que a razão 4:180 sugere — das
  180 invocações de `dev`, só **36** tocaram UI ou rota/API; nas outras 144 (Python, script,
  config) o `tester` não se aplica. Faltaram **~32 validações**, não 176.
- **Custo:** `dev` que valida a si mesmo rodou 84 turnos de mediana contra 32 de quem não
  valida, e 20% deles estouraram 121+ turnos (US$ 334, 39% do custo do grupo). Validar dentro
  do `dev` é caro porque a iteração "sobe → testa → falha → corrige → sobe" acontece no
  contexto que é reenviado inteiro a cada turno. No `tester` esse mesmo ciclo roda em contexto
  limpo, que é descartado no fim.

**A causa raiz é esta skill não ser lida.** Ela foi carregada **6 vezes em 38 sessões (16%)** —
sem ela o orquestrador improvisa o ciclo, e o `tester` é o primeiro passo a cair. Por isso a
regra agora não depende de você ter lido nada:

- um hook **bloqueia** o `dev` de subir a aplicação, rodar browser/E2E, tirar screenshot e
  bater na app por HTTP (ele mantém `tsc`/`build`/lint/teste unitário e qualquer script
  próprio, inclusive em background — é o `build_ok` que ele reporta);
- outro hook, no retorno de cada `dev`, **injeta um lembrete** quando os arquivos alterados
  incluem UI ou rota — no instante exato em que a decisão é sua.

Logo: **toda tarefa com UI, rota ou endpoint precisa de uma invocação de `tester`.** Se você
não invocar, ninguém validou. Use os `comandos_para_subir` que o `dev` devolveu.

Tarefa sem nada observável (refactor puro, tipo, script interno) segue sem `tester` — a prova
ali é o `build_ok` e a leitura do diff.

## Briefing para o `tester` (curto e focado)

O `tester` valida **apenas** o que a tarefa implementou (não a suite inteira). Passe:

- **Como subir** o app (use `comandos_para_subir` que o `dev` retornou).
- **O que validar**: rotas/páginas/estados específicos desta tarefa.
- **Screenshots**: nomeie **quais** capturar, com teto explícito (*"no máximo 2: a lista com
  dados em desktop e o estado de erro"*). Tarefa sem UI → *"nenhuma print; valide por
  resposta da API"*. O teto máximo dele é 5. Print custa ~1% do loop, então o teto serve para
  manter o `tester` focado no que a tarefa mudou — **não** para economizar: aprovar errado e
  devolver a tarefa ao `dev` custa muito mais que uma imagem.
- **Skills a consultar**: 1–2, como no briefing do `dev`.

Ele retorna:
```json
{ "veredito": "PASSOU|FALHOU", "falhas": [{ "tipo": "...", "tela": "...", "descricao": "..." }],
  "screenshots": ["/caminho/abs/..."], "logs_relevantes": [...], "recomendacao_para_dev": "..." }
```

## Avaliar e fechar o ciclo

- **PASSOU** → marque a tarefa `[x]` em `.forge/tasks.md`, registre o ciclo em
  `.forge/progress.md` (retorno do dev + veredito + **descrição** das falhas visuais, se
  houve; não os caminhos das imagens) e vá para a próxima tarefa. Registre em 2–4 linhas —
  `progress.md` é lido em toda retomada, então prolixidade ali é custo recorrente.
- **FALHOU** → monte um briefing de correção a partir de `falhas` + `recomendacao_para_dev`
  e volte a invocar o `dev`. Incremente a contagem de tentativas da tarefa em `progress.md`.
- **PARCIAL** (do `dev`, antes do tester) → re-loteie como descrito em "Revisão do retorno do
  dev". Se o que ele fechou já é testável por si, mande o `tester` nesse pedaço em paralelo
  com o `dev` da continuação.

Feche por tarefa, **não** espere o lote inteiro: cada tarefa que passa já é marcada e libera
o que dependia dela. E antes de disparar o próximo lote, rode o **checkpoint de paralelismo**
de novo — o que era serial pode ter destravado, e a correção de um FALHOU quase sempre roda
em paralelo com o lote seguinte.

## ⚠️ Regra do Loop Travado

Conte as tentativas por tarefa em `.forge/progress.md`.

- Mesmo erro na **3ª tentativa** → **reformule o briefing do zero**, por um ângulo diferente
  (outra abordagem técnica), e acione `search-before-code` (pesquisar o erro exato + ano atual).
- Persistindo após a reformulação → **pare e pergunte ao usuário**. Você é a sessão principal,
  então basta uma mensagem normal — não há "terminal preso" de onde escapar.

Nunca fique em loop infinito re-briefando a mesma coisa.

## Servidores de longa duração

Quando o `tester` precisar subir backend/frontend, ele usa `Bash` com `run_in_background: true`
e lê o output depois. Não existe mais a sessão tmux `servers`; não há foreground travando nada.

## Regras de ouro

- O usuário fala só com você. Nunca diga "abra o terminal" ou "fale com o dev".
- Você **não escreve código de produto** — sempre delega ao `dev`.
- Reporte ao usuário de forma resumida: o que foi feito, o que está em andamento, o que falta.
- Se o usuário mudar de ideia no meio, adapte o `tasks.md`.
- **Nunca deixe um subagente ocioso enquanto há trabalho independente na fila.** Se o usuário
  perguntar "tem algo a mais que outro subagente possa adiantar?", a resposta já deveria ser
  "sim, e já está rodando" — a pergunta é sinal de que você esqueceu o checkpoint.

## Custo — o que sai caro neste loop (medido, não estimado)

Os 35 transcripts deste repo (ago–set/2026) foram medidos: 2,65 bilhões de tokens
processados, dos quais **55% são os subagentes**. Dentro dos subagentes, **55% do custo é
`cache_read`** — contexto reenviado turno a turno.

O ponto contraintuitivo: é verdade que cada `dev` **começa** com contexto limpo, mas ele não
**permanece** limpo. O custo não desaparece no fan-out — ele migra para dentro do subagente,
onde cresce mais rápido porque ninguém o poda:

| turnos na invocação | n | custo médio/invocação | tokens processados/invocação |
|---|---|---|---|
| 1–10 | 5 | US$ 0,04 | 26 mil |
| 11–30 | 21 | US$ 1,09 | 777 mil |
| 31–60 | 49 | US$ 2,61 | 2,29 mi |
| 61–120 | 93 | US$ 5,65 | 6,83 mi |
| **121+** | **38** | **US$ 14,64** | **22,35 mi** |

Da primeira faixa à última: **366× por invocação.** Confira você mesmo com `bin/forge-tokens`.

O `dev` rodava com **mediana de 76 turnos** (p90 138, máximo 301). Por isso existe o teto por
hook: ele responde por ~76% da conta de subagentes. **Sua decomposição é a alavanca de custo
mais forte do Forge** — mais que modelo, mais que print, mais que qualquer ferramenta.

| Fonte | Peso medido | Regra |
|---|---|---|
| **Turnos por invocação** | o dominante | Tarefa atômica de verdade; `PARCIAL` no teto e re-loteio |
| **Bash** | 61% do que os subagentes ingeriram | No briefing: `Grep`/`Glob`/`Read` em vez de `grep`/`find`/`cat`; filtrar na fonte |
| **`Read` de arquivo inteiro** | 31% do ingerido; 74% das leituras sem `limit` | No briefing: nomeie os arquivos e mande usar `limit`/`offset`; proíba releitura |
| **Modelo** | opus custou 2,8× sonnet por invocação | `sonnet` padrão; opus só em arquitetura/Loop Travado |
| **Lote acoplado** | retrabalho é o pior desperdício | Arquivos disjuntos, teto de 3–4 |
| **Screenshots** | **~1%** — não é o vilão | Teto de 5/tarefa; você lê só o JSON. Não corte validação para "economizar" |

**Paralelismo NÃO está no custo.** Testei a hipótese do "subagent tax" (fan-out pagaria
`cache_write` a preço de cache frio) nos dados deste repo: `cache_write` por turno foi 3.448
em invocações solo e 3.349 em lote. Sem penalidade detectável. Mantenha o Invariante 5.

Quando o usuário estiver ajustando custo da sessão: decompor tarefas e revisar JSON não
precisa de effort alto — `/effort medium` serve. Guarde `high`/`xhigh` para quando você
estiver de fato raciocinando sobre arquitetura ou destravando um Loop Travado.
