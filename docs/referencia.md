# Referência técnica

O [`README`](../README.md) explica o Forge em linguagem simples. Aqui ficam os detalhes:
papéis e modelos, modos do `tester`, comandos, skills, hooks, invariantes, tetos de turnos,
variáveis de ambiente, workflows, estrutura do repositório e testes.

## Como funciona

### Os papéis

| Papel | Modelo | Pode | Não pode |
|---|---|---|---|
| orquestrador (a sessão principal) | o da sessão | Levantar requisitos, escrever a spec, decompor, briefar, despachar e revisar | Escrever código de produto (só `.forge/**`, `prompt.md`, `*.md`; `templates/*` só na fábrica; fora da raiz do projeto, `*.log`, `*.patch` e similares também são livres) |
| `dev` | sonnet | Escrever todo o código de produto; rodar `tsc`/build/lint e teste unitário (dali sai o `build_ok` que ele reporta) | Subir servidor, rodar browser/E2E, tirar screenshot ou bater na app por HTTP |
| `tester` | sonnet | Validar a entrega e emitir o veredito (`PASSOU`/`FALHOU`/`BLOQUEADO`) | Escrever código de produto (o `Write` dele serve só para spec de teste e evidência) |
| `scout` | haiku | Ler, varrer, pesquisar lib/API na web e mapear estrutura em volume; só o resumo volta ao orquestrador | Escrever ou editar arquivo, instalar dependência, alterar estado |

O `tester` trabalha em dois modos:

- **`browser`**: valida a UI no Chrome real via `claude-in-chrome`. Sempre serial e com teto
  de 5 evidências visuais por tarefa.
- **`contrato`**: sem navegador. Sobe o MCP server em stdio e chama as tools com payload
  real, roda a suíte do pacote tocado, confere infraestrutura **só por leitura** e compara o
  resultado com o critério de aceite.

O hook `require-tester.py` lê o retorno estruturado do `dev` (arquivos alterados e comandos
para subir) e recomenda o modo. O orquestrador decide e avisa em uma linha; não pergunta.

Como o `Agent` é assíncrono (o retorno chega depois, como notificação), a decisão vem do evento
`SubagentStop`, que dispara em qualquer profundidade: ele anota a entrega do `dev` e aplica o
veredito do `tester`. Quando o orquestrador tenta encerrar o turno (`Stop`) com entrega sem
`tester`, o hook **bloqueia uma vez** o fim do turno. Não bloqueia enquanto houver `dev` ou
`tester` do Forge ainda rodando. Cada entrega é cobrada uma só vez, e `stop_hook_active` libera
sempre, para nunca entrar em laço. Os vereditos:

- `PASSOU` limpa só as entregas cujos arquivos o briefing do `tester` cita; se nenhuma for
  citada, limpa a mais antiga;
- `FALHOU` e `BLOQUEADO` mantêm a pendência e reabrem a cobrança (`BLOQUEADO` não é aprovação).

**A raiz é quem não tem `agent_id`.** O payload de subagente traz `agent_id`; o da sessão
principal não. Os hooks usam essa ausência para reconhecer a raiz (contenção de escrita,
`volta-pasta-base`, `rtk-root`, `Stop` e o contador de turnos, que ignora a raiz).

### Comandos

- `/forge`: hub. Cria um projeto do zero, entra no modo fix de um existente ou investiga algo
  sem escrever código (incidente, banco, custo, infraestrutura). Também responde como
  `/forge:forge`.
- `/forge:new`: atalho direto para criar um projeto do zero.
- `/forge:fix`: atalho direto para o modo fix/implementação de um projeto existente.
- `/forge:setup`: prepara o repositório atual. Grava as `permissions` em
  `.claude/settings.json` e os invariantes no `CLAUDE.md` (entre marcadores, então rodar de
  novo atualiza em vez de duplicar). Oferece criar a fábrica, instalar o `rtk` e **perguntar**
  se você quer um mapa local de credenciais em `~/.claude/skills/credenciais-ambiente/SKILL.md`
  (perfis de nuvem de qualquer provedor, contas `gh`, tokens de API, service accounts; só
  ponteiros, nunca o segredo). Nunca sobrescreve nada em silêncio.
- `/forge:doctor`: diagnostica contexto, permissions, invariantes, hooks, `rtk` e se o
  `tester` enxerga o navegador. Só lê.

### Skills

O plugin traz 15 skills. Cada briefing nomeia só 1 ou 2 delas, para não encher o contexto.

| Skill | Para que serve |
|---|---|
| `banco-de-dados-leitura-segura` | Consultar banco ou data lake com perfil somente leitura, `LIMIT` na exploração e cuidado com PII em log ou relatório |
| `clean-code` | Princípios de código limpo ao escrever ou revisar: nomes, funções, DRY, KISS, erros e organização |
| `e2e-chrome` | Validar a UI de ponta a ponta no Chrome real, via `claude-in-chrome`, no modo `browser` do `tester` |
| `git-profiles` | Descobrir as contas git/GitHub da máquina, escolher a correta com o usuário e aplicá-la |
| `lessons-learned` | Erros e armadilhas recorrentes em projetos web (async, SQLite, upload, renderização, UX, processo) |
| `meta-prompt` | Conduzir a conversa que extrai requisitos e gerar um `prompt.md` auto-contido (fluxo "criar do zero") |
| `no-deploy-no-push` | O que exige autorização explícita antes de deploy, `git push` ou criar repositório; commits em português |
| `orchestrator` | Decompor em tarefas, montar briefings, invocar `dev`, `tester` e `scout`, avaliar retornos e persistir progresso |
| `safe-operations` | Conferir processos ativos antes de derrubar algo, atualizar a branch antes de analisá-la e filtrar saída grande |
| `scaffolding` | Estrutura inicial de projeto novo: pastas, `package.json`, TypeScript estrito, Vite + Tailwind, proxy, `.gitignore` |
| `search-before-code` | Pesquisar na web (com o ano) diante de erro de execução ou de tecnologia nova no projeto |
| `seguranca` | Regras de segurança antes de ação crítica: infraestrutura real, comando destrutivo, escopo e segredos |
| `setup-blocos` | Blocos canônicos do `/forge:setup`: `permissions`, invariantes, mapa de credenciais, merge e instalação do `rtk` |
| `spec-driven` | Ler o prompt como especificação: critérios de sucesso, contrato de saída, tarefas auto-contidas e aceite Given/When/Then |
| `testing-strategy` | Escopo de teste de uma mudança: o que mudou, não o projeto inteiro; ordem de execução e anti-padrões |

### Os dois jeitos de usar

- **Fábrica**: uma pasta base com `projects/` dentro. Cada repositório em que você trabalha é
  clonado para lá e você conversa sempre com **um** orquestrador, na raiz da base. Projeto
  novo nasce em `projects/<nome>/`, com git próprio. O `/forge:setup` cria a pasta.
- **Repo atual**: o plugin instalado e `/forge` rodado dentro do repositório onde você já
  trabalha; o controle fica em `.forge/` na raiz dele.

A detecção é automática, em três modos:

- **fábrica:** a raiz tem `projects/` **e** `templates/prompt.template.md`;
- **projeto da fábrica:** a sessão está aberta em `<fábrica>/projects/<nome>/` (ou numa subpasta
  dele). O `CLAUDE.md` da fábrica é herdado (o Claude Code lê os das pastas acima) e os hooks
  valem ali. A escrita fica contida no projeto, para o orquestrador e para os subagentes: fora
  da pasta do projeto só passam `/tmp`, `$TMPDIR` e as pastas `~/.claude*`. Dentro do projeto
  valem as mesmas regras do repo atual;
- **repo atual:** qualquer outro caso.

Abra a sessão na raiz da fábrica só para criar projeto novo, para trabalho que cruza projetos e
para a manutenção do próprio Forge.

### Hooks

Definidos em `plugins/forge/hooks/hooks.json`. Os scripts `.sh` são chamados via `bash` e o
`.py` via `python3`, sem depender de bit de execução.

| Hook | Evento | O que faz |
|---|---|---|
| `deny-orchestrator-code-edits.sh` | PreToolUse `Write\|Edit\|NotebookEdit` | Bloqueia o orquestrador de escrever código de produto; subagentes escrevem livremente. No modo projeto da fábrica, contém a escrita no projeto (orquestrador e subagentes) |
| `subagent-turn-budget.sh` | PreToolUse e PostToolUse em `Bash`, `Read`, `Edit`, `Write`, `Glob`, `Grep`, `WebSearch`, `WebFetch` e `mcp__*` | Conta as chamadas de ferramenta de cada subagente (as `mcp__*` contam para `dev`, `tester` e `scout`), avisa e depois nega no teto do papel; nega ao `dev` subir servidor de aplicação (servidores web conhecidos, `pnpm`/`npm dev`, `start`, `preview`, `serve`, e scripts `app`/`server`/`index`/`main` em Python e Node), browser, screenshot ou `curl` local; delega Bash de leitura ao `rtk` quando ele existe. Ignora a raiz |
| `volta-pasta-base.py` | PreToolUse `Bash` | Na sessão principal (sem `agent_id`), se a cwd do shell divergir de `CLAUDE_PROJECT_DIR`, reescreve o comando com `cd "<raiz>" &&` e avisa |
| `rtk-root.sh` | PreToolUse `Bash` | Na sessão principal, encadeia o `rtk` (opcional); é o único escritor de `updatedInput` quando a cwd está na raiz. É o único que delega o Bash da raiz ao `rtk`: o `subagent-turn-budget.sh` só delega o dos subagentes |
| `require-tester.py` | `SubagentStop`, `Stop` e PostToolUse `Agent` | `SubagentStop`: anota a entrega do `dev` (o modo vem do retorno estruturado) e aplica o veredito do `tester`, em qualquer profundidade. `Stop` da raiz: bloqueia uma vez o fim do turno com entrega sem `tester`. `PostToolUse(Agent)`: marca o `tester` lançado (`async_launched`) e cobre CLIs de término síncrono |
| `delega-varredura.py` | PostToolUse | Conta leituras consecutivas do orquestrador (inclusive chamadas MCP) e, a partir de 8 (`FORGE_LEITURA_LIMIAR`), lembra de delegar ao `scout` |
| `deny-orchestrator-bash-writes.py` | PreToolUse `Bash` | Barra a escrita de código pela sessão principal via Bash (e, no modo projeto da fábrica, a escrita fora do projeto), com as mesmas regras de caminho do `Write\|Edit\|NotebookEdit` |
| `git-identidade-local.py` | PreToolUse `Bash` | Nega `git commit` em repo sem `user.email` local |

### Invariantes

O `/forge:setup` grava estes seis no `CLAUDE.md` do repositório (a fábrica ganha mais dois,
sobre onde os projetos vivem):

1. Não escreva código de produto; delegue ao `dev`.
2. Nunca `git push` nem deploy de qualquer tipo (infra, container, serverless, cloud) por
   conta própria; só sob ordem explícita. Antes de aplicar infra, mostre o diff ou plano.
3. Commits em português do Brasil (prefixos convencionais em inglês são ok).
4. Segurança de processos: confira processos ativos antes de matar ou reiniciar, pesquise
   tecnologia nova incluindo o ano na busca, pergunte o perfil git se não foi especificado.
5. Paralelize por padrão: o que for independente vai na mesma mensagem.
6. Cada token reenviado é pago de novo: decomponha em tarefas pequenas, nomeie 1-2 skills por
   briefing, prefira `Read` para arquivo conhecido e `command grep -rn`/`find` com filtro e limite para busca.

O `deny` das permissions é só o mínimo genérico (`git push --force`, `-f`,
`--force-with-lease`); `git push` comum cai no `ask`. A regra de deploy vive no invariante 2,
não numa lista de comandos de um provedor.

## Economia de token

O gasto dominante de um loop de agentes é o **contexto reenviado**: a cada turno a invocação
inteira volta para o modelo, e ela só cresce. Por isso o mesmo turno custa mais no fim de uma
invocação longa do que numa curta: invocações longas reenviam o contexto a cada turno e ficam
caras. A sessão principal também pesa na conta, porque
acumula tudo o que lê. Por isso existem o `scout` (a varredura morre com ele) e o
`delega-varredura.py`. Os números variam por pessoa e por projeto: meça os seus com
`forge-tokens`, seguindo [`docs/linha-de-base.md`](linha-de-base.md).

Cada invocação tem um teto de chamadas de ferramenta, imposto por `subagent-turn-budget.sh`,
com valor próprio para cada papel. No teto, o `dev`, o `scout` e os papéis genéricos devolvem `status: "PARCIAL"`; o `tester`
devolve `FALHOU` se já achou defeito do produto, ou `BLOQUEADO` (`teto de turnos esgotado`) se
não achou nenhum. O orquestrador re-loteia sem perder o que já foi feito; não é falha.

| Papel | Aviso | Teto | Variáveis de ambiente |
|---|---|---|---|
| `dev` | 25 | 35 (≈60 turnos) | `FORGE_TURN_WARN` / `FORGE_TURN_CAP` |
| `tester` | 180 | 250 | `FORGE_TESTER_WARN` / `FORGE_TESTER_CAP` |
| `scout` | 28 | 40 | `FORGE_SCOUT_WARN` / `FORGE_SCOUT_CAP` |
| genérico (`general-purpose`, `Explore`, agentes de outros plugins) | 30 | 40 | `FORGE_OUTRO_WARN` / `FORGE_OUTRO_CAP` |
| agente de construção visual (plugin `forge-visual`, se instalado) | 100 | 130 | `FORGE_VISUAL_WARN` / `FORGE_VISUAL_CAP` |
| `tester` do `forge-visual` | 50 | 70 | `FORGE_VISUAL_TESTER_WARN` / `FORGE_VISUAL_TESTER_CAP` |

As chamadas `mcp__*` (por exemplo, as do navegador) entram na conta de `dev`, `tester` e
`scout`; agentes genéricos e visuais as ignoram. O `tester` tem teto alto porque sobe
servidor, roda E2E e dirige o navegador: o teto serve para pegar fuga de controle, não para
apertar.

### Variáveis de ambiente

Todas opcionais. Valor inválido cai no padrão.

| Variável | Efeito |
|---|---|
| `FORGE_TURN_WARN` / `FORGE_TURN_CAP` | Aviso e teto de chamadas do `dev` (padrão 25 / 35) |
| `FORGE_TESTER_WARN` / `FORGE_TESTER_CAP` | Aviso e teto do `tester` (padrão 180 / 250) |
| `FORGE_SCOUT_WARN` / `FORGE_SCOUT_CAP` | Aviso e teto do `scout` (padrão 28 / 40) |
| `FORGE_OUTRO_WARN` / `FORGE_OUTRO_CAP` | Aviso e teto dos agentes genéricos (padrão 30 / 40) |
| `FORGE_VISUAL_WARN` / `FORGE_VISUAL_CAP` | Aviso e teto dos agentes `forge-visual:*` que constroem (padrão 100 / 130) |
| `FORGE_VISUAL_TESTER_WARN` / `FORGE_VISUAL_TESTER_CAP` | Aviso e teto dos `tester` do `forge-visual` (padrão 50 / 70) |
| `FORGE_LEITURA_LIMIAR` | Quantas leituras consecutivas do orquestrador disparam o lembrete de delegar ao `scout` (padrão 8) |
| `FORGE_RTK_BIN` | Caminho do binário `rtk`; sem ela, os hooks procuram `rtk` no `PATH` e, não achando, seguem sem delegar |
| `FORGE_STATE_DIR` | Diretório de estado dos hooks (contadores de turno e de leitura, pendência de validação). Sem ela, cada hook usa `$XDG_RUNTIME_DIR`, `$TMPDIR` ou `/tmp`, sob `forge/<turns, leituras ou validacao>/<session_id>`. Nunca grava dentro do repositório; contadores com mais de um dia são apagados |
| `FORGE_VOLTA_COMPOSE` | Uso interno: o `volta-pasta-base.py` define `1` ao chamar o `rtk-root.sh`, para obter o comando já reescrito pelo `rtk` e prefixar o `cd`. Não precisa ser definida à mão |

## Workflows

Dois workflows do plugin, declarados em `plugin.json` (campo `workflows`) e chamados pelo
`/forge` pela ferramenta **Workflow**. Também respondem como `/forge:executar-lote` e
`/forge:investigar`. Os testes em `workflows/tests/` ficam fora da lista de propósito.

### `forge:executar-lote`

Roda um lote de tarefas no ciclo `forge:dev` → `forge:tester` → correção.

- **`args`:** `{ "tarefas": [{ "id", "briefing_dev", "teste": "browser" | "contrato" | "nenhum",
  "briefing_tester" }], "max_tentativas": 3 }`. `briefing_tester` é obrigatório quando `teste`
  não é `nenhum`; `max_tentativas` é opcional (inteiro ≥ 1, padrão 3).
- **Como roda:** um `dev` por tarefa, em paralelo; `tester` em modo `browser` entram em fila (um
  Chrome só) e os de `contrato` rodam em paralelo. No `FALHOU`, o `dev` recebe as falhas e a
  recomendação do `tester` e tenta de novo, até o máximo.
- **Retorno:** uma lista com, por tarefa, `id`, `status_final` (`PASSOU`, `FALHOU`,
  `BLOQUEADO`, `PARCIAL` ou `SEM_TESTE`), `tentativas`, `dev`, `tester` e `proximo_briefing`.
- **Cuidados:** as tarefas de um mesmo lote precisam ter arquivos disjuntos, e o workflow não
  pergunta nada ao usuário no meio.

### `forge:investigar`

Investigação somente leitura com `forge:scout`.

- **`args`:** `{ "pergunta": "...", "frentes": [{ "titulo": "...", "escopo": "..." }] }`.
- **Como roda:** um `scout` por frente; depois, um `scout` cético por achado (até 8 por frente)
  tenta refutá-lo lendo o lugar citado; por fim, um `scout` aponta as lacunas.
- **Retorno:** `{ pergunta, frentes, lacunas }`; cada frente traz `resposta`,
  `achados_confirmados`, `achados_refutados` e `achados_nao_verificados`.

### Permissão e aprovação

O `/forge:setup` libera `Workflow(forge:executar-lote)` e `Workflow(forge:investigar)` no
`allow`. A forma com namespace de plugin ainda não foi testada: se a liberação não casar, o
Claude Code pede aprovação na primeira chamada, e a opção **"Yes, and don't ask again"** resolve
dali em diante. O acompanhamento fica em `/workflows`.

### Fallback manual

Com a ferramenta Workflow ausente ou desligada (`disableWorkflows`, CLI antiga), o `/forge`
faz o mesmo à mão com `Agent`: `dev` → `tester` → avaliação, um `Agent` por tarefa na mesma
mensagem (e um `scout` por frente na investigação). O retorno chega depois, como notificação,
e o `require-tester` barra o fim do turno se houver entrega sem `tester`.

O teto do `dev` é conservador de propósito: apertar demais corta tarefas no meio, e o
retrabalho de uma tarefa partida no meio custa mais que a economia. Também por custo, `dev` e
`tester` ficam em sonnet. Para medir o seu uso, rode
`plugins/forge/bin/forge-tokens --desde AAAA-MM-DD` e compare antes e depois.

O `rtk` é opcional; os hooks degradam em silêncio sem o binário. O ganho dele varia
conforme o perfil de comandos de cada projeto; vale medir (`docs/linha-de-base.md`,
`forge-tokens`). As regras de briefing (`Read` para arquivo conhecido, `command grep -rn`/`find`
com filtro e limite, filtrar na fonte) atacam a mesma causa, o contexto acumulado, e valem com
ou sem o `rtk`.

O repositório não traz medição própria: o ganho dos tetos e dos hooks só está provado na sua
máquina depois que você medir antes e depois.

## Estrutura do repositório

```
.claude-plugin/marketplace.json     # catálogo: forge e forge-frontend
plugins/forge/
  .claude-plugin/plugin.json
  agents/                           # dev.md, tester.md, scout.md
  commands/                         # forge, new, fix, setup, doctor
  skills/                           # 15 skills: orchestrator, setup-blocos, no-deploy-no-push,
                                    #   safe-operations, spec-driven, e2e-chrome, testing-strategy, ...
  hooks/                            # hooks.json, scripts, lib/ e tests/
  workflows/                        # executar-lote.js, investigar.js e tests/
  evals/                            # avaliação de comportamento (1 caso)
  bin/forge-tokens                  # mede consumo a partir dos transcritos
  templates/                        # prompt.template.md e .npmrc
plugins/forge-frontend/             # 10 skills de frontend (opcional)
docs/                               # tutorial, referência, apresentação para equipe, linha de base, assets do README
```

## Desenvolvimento

Testes dos hooks (biblioteca padrão, um script por hook, 121 casos no total):

```bash
for t in plugins/forge/hooks/tests/test_*.py; do python3 "$t"; done
```

Os scripts são `test_delega_varredura.py` (10 casos), `test_deny_bash_writes.py` (15),
`test_deny_orchestrator.py` (23), `test_identidade_local.py` (8), `test_require_tester.py` (32,
construídos a partir de payloads reais de `PostToolUse`, `SubagentStop` e `Stop` capturados na
CLI), `test_subagent_turn_budget.py` (19) e `test_volta_pasta_base.py` (14).

Os workflows têm 7 cenários, que rodam no `node` (sem rede e sem modelo):

```bash
node plugins/forge/workflows/tests/test_workflows.mjs
```

Validação estática dos manifestos, sem custo:

```bash
claude plugin validate .
```

A suíte de **comportamento** em `plugins/forge/evals/` verifica o que instrução em markdown não
garante sozinha; hoje é um caso, `investigacao-nao-vira-codigo` (uma investigação não pode
virar loop de escrever código). Rodar custa tokens, porque cada caso é uma execução de modelo.

### O que ainda não foi verificado

O `tester` em modo `browser` depende das ferramentas do `claude-in-chrome`. O frontmatter de
`plugins/forge/agents/tester.md` omite o campo `tools`, então o subagente herda as da sessão,
incluindo as do MCP. Que isso entrega o navegador ao `tester` ainda não foi provado em
execução; o `/forge:doctor` faz essa verificação. Sem o navegador, o modo `contrato` funciona
normalmente.
