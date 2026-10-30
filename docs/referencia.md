# Referência técnica

O [`README`](../README.md) explica o Forge em linguagem simples. Aqui ficam os detalhes:
papéis e modelos, modos do `tester`, comandos, hooks, invariantes, tetos de turnos, estrutura
do repositório e testes.

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
para subir) e recomenda o modo. O orquestrador decide e avisa em uma linha; não pergunta. O mesmo hook guarda
a pendência de validação da sessão e trata o veredito do `tester`: `PASSOU` a limpa, `FALHOU` e
`BLOQUEADO` a mantêm.

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

### Os dois jeitos de usar

- **Fábrica**: uma pasta base com `projects/` dentro. Cada repositório em que você trabalha é
  clonado para lá e você conversa sempre com **um** orquestrador, na raiz da base. Projeto
  novo nasce em `projects/<nome>/`, com git próprio. O `/forge:setup` cria a pasta.
- **Repo atual**: o plugin instalado e `/forge` rodado dentro do repositório onde você já
  trabalha; o controle fica em `.forge/` na raiz dele.

A detecção é automática: é fábrica quando a raiz tem `projects/` **e**
`templates/prompt.template.md`; qualquer outro caso é repo atual.

Abra a sessão sempre na raiz, da fábrica ou do repositório preparado. Nunca direto dentro de
`projects/<nome>/`: esse diretório não tem o `CLAUDE.md` nem as `permissions` do Forge, e não
há garantia de que os hooks disparem ali.

### Hooks

Definidos em `plugins/forge/hooks/hooks.json`. Os scripts `.sh` são chamados via `bash` e o
`.py` via `python3`, sem depender de bit de execução.

| Hook | Evento | O que faz |
|---|---|---|
| `deny-orchestrator-code-edits.sh` | PreToolUse `Write\|Edit` | Bloqueia o orquestrador de escrever código de produto; subagentes escrevem livremente |
| `subagent-turn-budget.sh` | PreToolUse e PostToolUse | Conta as chamadas de ferramenta de cada subagente, avisa e depois nega no teto do papel; nega ao `dev` subir servidor, browser, screenshot ou `curl` local; delega Bash de leitura ao `rtk` quando ele existe |
| `volta-pasta-base.py` | PreToolUse `Bash` | Na sessão principal, se a cwd do shell divergir de `CLAUDE_PROJECT_DIR`, reescreve o comando com `cd "<raiz>" &&` e avisa |
| `rtk-root.sh` | PreToolUse `Bash` | Na sessão principal, encadeia o `rtk` (opcional); é o único escritor de `updatedInput` quando a cwd está na raiz |
| `require-tester.py` | PostToolUse `Agent` | Ao fim de cada `dev`, decide se o `tester` é obrigatório e em qual modo, pelo retorno estruturado dele; também guarda a pendência de validação e trata os vereditos do `tester` |
| `delega-varredura.py` | PostToolUse | Conta leituras consecutivas do orquestrador (inclusive chamadas MCP) e, a partir de 8 (`FORGE_LEITURA_LIMIAR`), lembra de delegar ao `scout` |
| `deny-orchestrator-bash-writes.py` | PreToolUse `Bash` | Barra a escrita de código pela sessão principal via Bash, com as mesmas regras de caminho do `Write\|Edit` |
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
| `tester` | 45 | 65 | `FORGE_TESTER_WARN` / `FORGE_TESTER_CAP` |
| `scout` | 28 | 40 | `FORGE_SCOUT_WARN` / `FORGE_SCOUT_CAP` |
| genérico (`general-purpose`, `Explore`, agentes de outros plugins) | 30 | 40 | `FORGE_OUTRO_WARN` / `FORGE_OUTRO_CAP` |

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
  evals/                            # avaliação de comportamento (1 caso)
  bin/forge-tokens                  # mede consumo a partir dos transcritos
  templates/                        # prompt.template.md e .npmrc
plugins/forge-frontend/             # 10 skills de frontend (opcional)
docs/                               # tutorial, referência, apresentação para equipe, linha de base, assets do README
```

## Desenvolvimento

Testes dos hooks (biblioteca padrão, um script por hook, 92 casos no total):

```bash
for t in plugins/forge/hooks/tests/test_*.py; do python3 "$t"; done
```

Os scripts são `test_delega_varredura.py` (10 casos), `test_deny_bash_writes.py` (8),
`test_deny_orchestrator.py` (12), `test_identidade_local.py` (8), `test_require_tester.py` (25,
construídos a partir de payloads reais de `PostToolUse` capturados na CLI),
`test_subagent_turn_budget.py` (16) e `test_volta_pasta_base.py` (13).

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
