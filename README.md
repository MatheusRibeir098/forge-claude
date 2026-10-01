# Forge

Marketplace pessoal de plugins para o Claude Code. O plugin `forge` é uma fábrica de software
movida a subagentes: você conversa com **um orquestrador**, que levanta requisitos, monta a
spec, quebra o trabalho em tarefas e despacha `dev`, `tester` e `scout`. A divisão de papel
não é convenção que o modelo pode esquecer no meio da conversa: é **imposta por hook**, e cada
invocação de subagente tem um teto de turnos calibrado por medição. O `forge-frontend` é um
complemento opcional com skills de interface para o `dev`.

## Início rápido

Pré-requisitos:

- Claude Code.
- `python3` no `PATH` (os hooks usam; só biblioteca padrão).
- `git`, e `node` com `pnpm` se o `dev` for criar ou tocar projetos JavaScript.
- Opcional: [`rtk`](https://github.com/rtk-ai/rtk), que comprime a saída de comandos (o
  `/forge:setup` oferece instalar).
- Opcional: a extensão `claude-in-chrome`, necessária só para o `tester` em modo `browser`.

Dentro do Claude Code:

```
/plugin marketplace add MatheusRibeir098/forge-claude
/plugin install forge@forge-claude
/plugin install forge-frontend@forge-claude     # opcional, só para trabalho com interface
```

Depois, no repositório onde você vai trabalhar:

```
/forge:setup      # grava permissions e invariantes (mostra o diff e pede confirmação)
/forge:doctor     # confere o ambiente; só lê, não altera nada
/forge            # começa
```

Passo a passo de uso, com exemplos de pedido real: [`docs/tutorial.md`](docs/tutorial.md).

## Como funciona

### Os papéis

| Papel | Modelo | Pode | Não pode |
|---|---|---|---|
| orquestrador (a sessão principal) | o da sessão | Levantar requisitos, escrever a spec, decompor, briefar, despachar e revisar | Escrever código de produto (só `.forge/**`, `prompt.md`, `*.md`, `templates/`) |
| `dev` | sonnet | Escrever todo o código de produto; rodar `tsc`/build/lint e teste unitário (dali sai o `build_ok` que ele reporta) | Subir servidor, rodar browser/E2E, tirar screenshot ou bater na app por HTTP |
| `tester` | sonnet | Validar a entrega e emitir o veredito (`PASSOU`/`FALHOU`) | Escrever código de produto (o `Write` dele serve só para spec de teste e evidência) |
| `scout` | haiku | Ler, varrer, pesquisar lib/API na web e mapear estrutura em volume; só o resumo volta ao orquestrador | Escrever ou editar arquivo, instalar dependência, alterar estado |

O `tester` trabalha em dois modos:

- **`browser`**: valida a UI no Chrome real via `claude-in-chrome`. Sempre serial e com teto
  de 5 evidências visuais por tarefa.
- **`contrato`**: sem navegador. Sobe o MCP server em stdio e chama as tools com payload
  real, roda a suíte do pacote tocado, confere infraestrutura **só por leitura** e compara o
  resultado com o critério de aceite.

O hook `require-tester.py` lê o retorno estruturado do `dev` (arquivos alterados e comandos
para subir) e recomenda o modo. O orquestrador decide e avisa em uma linha; não pergunta.

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
| `require-tester.py` | PostToolUse `Agent` | Ao fim de cada `dev`, decide se o `tester` é obrigatório e em qual modo, pelo retorno estruturado dele |
| `delega-varredura.py` | PostToolUse | Conta leituras consecutivas do orquestrador e, a partir de 8 (`FORGE_LEITURA_LIMIAR`), lembra de delegar ao `scout` |

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
   briefing, prefira `Grep`/`Glob`/`Read` a `grep`/`find`/`cat`.

O `deny` das permissions é só o mínimo genérico (`git push --force`, `-f`,
`--force-with-lease`); `git push` comum cai no `ask`. A regra de deploy vive no invariante 2,
não numa lista de comandos de um provedor.

## Economia de token

O gasto dominante de um loop de agentes é o **contexto reenviado**: a cada turno a invocação
inteira volta para o modelo, e ela só cresce. Medido em 30 dias de uso real (uma pessoa, 43
sessões; detalhes em [`docs/linha-de-base.md`](docs/linha-de-base.md)):

| Turnos na invocação | Custo médio | Custo por turno |
|---|---|---|
| 1-10 | US$ 0,08 | US$ 0,0139 |
| 31-60 | US$ 1,86 | US$ 0,0435 |
| 61-120 | US$ 5,97 | US$ 0,0724 |
| 121+ | US$ 21,93 | US$ 0,1205 |

O mesmo turno custa **8,7x mais** no fim de uma invocação longa do que numa curta. As 29
invocações acima de 60 turnos foram 8,8% do total e **metade** do custo dos subagentes. A
sessão principal fez 26% dos turnos e gastou 55% da conta, porque acumula tudo o que lê. Por
isso existem o `scout` (a varredura morre com ele) e o `delega-varredura.py`.

Cada invocação tem um teto de chamadas de ferramenta, imposto por `subagent-turn-budget.sh` e
calibrado pela **mediana** de cada papel (teto abaixo da mediana estrangula o agente e gera
retrabalho). No teto, o subagente devolve `status: "PARCIAL"` e o orquestrador re-loteia sem
perder o que já foi feito; não é falha.

| Papel | Aviso | Teto | Variáveis de ambiente | Mediana medida |
|---|---|---|---|---|
| `dev` | 25 | 35 (≈60 turnos) | `FORGE_TURN_WARN` / `FORGE_TURN_CAP` | 42 chamadas (74 turnos) |
| `tester` | 45 | 65 | `FORGE_TESTER_WARN` / `FORGE_TESTER_CAP` | 54 chamadas |
| `scout` | 28 | 40 | `FORGE_SCOUT_WARN` / `FORGE_SCOUT_CAP` | 6 chamadas |

O teto do `dev` é conservador de propósito: 35 chamadas atingem ~54% das invocações e
respondem por ~58% da conta de subagentes pela simulação. Apertar para 26 chegaria a ~76%,
mas corta acima da mediana, e o retrabalho de uma tarefa partida no meio custa mais que a
economia. Também por custo, `dev` e `tester` ficam em sonnet: com opus, a invocação saiu 2,8x
mais cara. Para medir o seu uso, rode `plugins/forge/bin/forge-tokens --desde AAAA-MM-DD` e
compare com a linha de base.

O `rtk` é opcional; os hooks degradam em silêncio sem o binário. O ganho dele foi modesto:
**~4,5%** do volume de Bash no perfil medido, longe dos "60-90%" anunciados. O ganho maior vem
das regras de briefing (`Grep`/`Glob`/`Read` no lugar de `grep`/`find`/`cat`, filtrar na
fonte).

Essas medições descrevem o comportamento **anterior** ao plugin e vêm de uma pessoa só; nada
foi medido depois dos hooks em produção.

## Estrutura do repositório

```
.claude-plugin/marketplace.json     # catálogo: forge e forge-frontend
plugins/forge/
  .claude-plugin/plugin.json
  agents/                           # dev.md, tester.md, scout.md
  commands/                         # forge, new, fix, setup, doctor
  skills/                           # 15 skills: orchestrator, setup-blocos, no-deploy-no-push,
                                    #   safe-operations, spec-driven, e2e-chrome, ...
  hooks/                            # hooks.json, scripts, lib/ e tests/
  evals/                            # avaliação de comportamento (1 caso)
  bin/forge-tokens                  # mede consumo a partir dos transcritos
  templates/                        # prompt.template.md e .npmrc
plugins/forge-frontend/             # 10 skills de frontend (opcional)
docs/                               # tutorial, apresentação para equipe, linha de base
```

## Desenvolvimento

Testes dos hooks (biblioteca padrão, um script por hook, 44 casos no total):

```bash
for t in plugins/forge/hooks/tests/test_*.py; do python3 "$t"; done
```

Os scripts são `test_require_tester.py` (15 casos, construídos a partir de payloads reais de
`PostToolUse` capturados na CLI), `test_delega_varredura.py`, `test_deny_orchestrator.py` e
`test_volta_pasta_base.py`.

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

## Origem e licença

O Forge foi derivado do plugin interno da Dati (`datisolucoesemti/dati-forge-plugin`). Aqui
saíram as skills, hooks, permissões e evals ligados a um provedor de nuvem específico; a
regra de deploy ficou genérica e o mapa de credenciais virou opcional. Entrou o hook
`volta-pasta-base.py`.

Licença MIT, em [`LICENSE`](LICENSE).
