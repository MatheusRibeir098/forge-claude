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
  ├─ revisa o retorno
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
  as abre** (imagem é o item mais caro do loop). Os caminhos ficam para o usuário.

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
   - completável numa única invocação do `dev`;
   - com critério de aceitação próprio (Given/When/Then — ver skill `spec-driven`);
   - listando os arquivos que serão criados/alterados;
   - dependendo só de tarefas anteriores.
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

Invoque o subagente `dev` passando esse briefing — **um por tarefa do lote, todos na mesma
mensagem**. Cada um retorna:
```json
{ "status": "OK|BLOQUEADO", "arquivos_alterados": [...], "build_ok": true,
  "comandos_para_subir": [...], "resumo": "...", "pendencias": [...] }
```

### Revisão do retorno do dev
- `status: BLOQUEADO` → leia `pendencias`. Se for decisão de produto, **pergunte ao usuário**.
- `build_ok: false` → re-briefe com foco no erro (e acione a skill `search-before-code`).
- Fora do escopo / código duvidoso → re-briefe apontando o desvio.
- **Lote com vários devs**: revise cada retorno e cruze os `arquivos_alterados`. Se dois
  agentes tocaram o mesmo arquivo, a partição falhou — inspecione o arquivo antes de seguir e
  corrija o lote no `tasks.md`. Um `dev` bloqueado **não** segura os irmãos: siga com os que
  voltaram OK.

## Briefing para o `tester` (curto e focado)

O `tester` valida **apenas** o que a tarefa implementou (não a suite inteira). Passe:

- **Como subir** o app (use `comandos_para_subir` que o `dev` retornou).
- **O que validar**: rotas/páginas/estados específicos desta tarefa.
- **Screenshots**: nomeie **quais** capturar, com teto explícito (*"no máximo 2: a lista com
  dados em desktop e o estado de erro"*). Tarefa sem UI → *"nenhuma print; valide por
  resposta da API"*. Sem teto, o `tester` captura demais e é o gasto mais caro do loop.
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

## Custo — o que sai caro neste loop

Paralelismo e economia não brigam: cada `dev` parte de **contexto limpo**, enquanto um agente
sequencial arrasta o histórico de todas as tarefas anteriores. Lotes trocam tokens por
latência no curto prazo e devolvem no longo, via isolamento. O que **de fato** encarece:

| Fonte | Por quê | Regra |
|---|---|---|
| **Screenshots** | Uma print pode custar mais que o briefing inteiro, e é reenviada a cada turno se entrar no contexto principal | Teto de 3/tarefa, sem `fullPage`; quem analisa é o `tester`; você lê só o JSON |
| **Output de comando** | Entra no contexto e é reenviado para sempre | Filtre na fonte (`safe-operations`) |
| **`progress.md`** | Lido a cada retomada; cresce sem limite se ninguém podar | Teto de ~10 ciclos + histórico à parte |
| **Skills não pedidas** | O subagente carrega por precaução | Nomeie 1–2 no briefing |
| **Lote acoplado** | Retrabalho é o desperdício mais caro que existe | Arquivos disjuntos, teto de 3–4 |

Quando o usuário estiver ajustando custo da sessão: decompor tarefas e revisar JSON não
precisa de effort alto — `/effort medium` serve. Guarde `high`/`xhigh` para quando você
estiver de fato raciocinando sobre arquitetura ou destravando um Loop Travado.
