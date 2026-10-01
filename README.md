# Forge

Plugin do Claude Code para a organização `datisolucoesemti`. Fábrica de software movida a
subagentes, com validação imposta por hook em vez de convenção.

## Início rápido

```
/plugin marketplace add datisolucoesemti/dati-forge-plugin
/plugin install forge@forge
/forge:setup      # no repositório onde você vai trabalhar
/forge:forge
```

Detalhe de cada passo em [Instalação](#instalação); como usar no dia a dia em
[`docs/tutorial.md`](docs/tutorial.md).

## O que é

Com o Forge você conversa com **um único orquestrador**. É ele quem levanta os requisitos,
monta a spec, quebra o trabalho em tarefas atômicas e despacha subagentes em paralelo para
executá-las. Quem escreve código é sempre o `dev`; quem valida se o que foi escrito realmente
funciona é sempre o `tester`; quem faz varredura e pesquisa em volume — sem sujar a conversa
principal — é o `scout`. Essa divisão de papel não é uma convenção que o modelo pode esquecer
no meio da conversa: ela é **imposta por hook**. Um hook bloqueia o orquestrador de escrever
código de produto; outro bloqueia o `dev` de validar a si mesmo (subir servidor, rodar
browser/E2E, tirar print, bater na app por HTTP); e cada invocação de subagente tem um teto de
turnos, calibrado por medição, que devolve o trabalho parcial em vez de deixar a invocação
fugir de controle.

Por que isso existe: o gasto dominante de um loop de agentes não é o volume de trabalho, é o
**contexto reenviado** — a cada turno, a invocação inteira volta para o modelo, e ela só
cresce. Medido em 30 dias de uso real (ver `docs/linha-de-base.md`): uma invocação de até 10
turnos custou **US$ 0,08**; uma de 121+ turnos, **US$ 21,93**. E o mesmo **turno** custa
**8,7× mais** no fim de uma invocação longa do que no começo de uma curta. As 29 invocações
que passaram de 60 turnos foram 8,8% do total e **metade** do custo de todos os subagentes.

O lado que costuma passar despercebido é a **sessão principal**: ela fez 26% dos turnos e
gastou 55% da conta, porque acumula tudo o que é lido e nunca poda. Por isso existe o `scout`,
e por isso um hook avisa quando o orquestrador emenda leituras em vez de delegar.

## Os três subagentes

| Papel | Modelo | Pode | Não pode |
|---|---|---|---|
| `dev` | sonnet | Escreve todo o código de produto; roda `tsc`/build/lint e teste unitário (é dali que sai o `build_ok` que ele reporta) | Subir servidor, rodar browser/E2E, tirar screenshot ou bater na app por HTTP — bloqueado por hook |
| `tester` | sonnet | Valida a entrega em dois modos (`browser`/`contrato`) e emite o veredito final — é a palavra final da validação | Escrever código de produto (o `Write` dele serve só para spec de teste e para salvar evidência) |
| `scout` | haiku | Lê, varre, pesquisa lib/API na web e mapeia estrutura em volume — o contexto da varredura morre com ele, só o resumo volta | Escrever ou editar qualquer arquivo, instalar dependência, alterar estado, decidir pelo usuário |

## O `tester` em dois modos

- **`browser`** — valida a UI no Chrome real do usuário via `claude-in-chrome`. Roda sempre
  **serial** (é o navegador real, uma janela só) e tem teto de **5 evidências visuais** por
  tarefa.
- **`contrato`** — sem navegador: sobe o MCP server em stdio e chama as tools de verdade com
  payload real, roda a suíte de teste completa do pacote tocado, confere infraestrutura AWS
  **só por leitura** (`describe-*`/`list-*`/`get-*`; nunca `create-*`/`update-*`/`delete-*`
  nem `deploy`/`apply`), e compara o resultado com o critério de aceite da tarefa.

Um hook lê o **retorno estruturado** do `dev` (os arquivos que ele alterou e os comandos para
subir) e recomenda automaticamente qual modo usar. O orquestrador não pergunta ao usuário qual
modo escolher — ele **decide e avisa** em uma linha.

## Instalação

### 1. Instalar o plugin (uma vez por máquina)

```
/plugin marketplace add datisolucoesemti/dati-forge-plugin
/plugin install forge@forge
```

O `forge-frontend` é **opcional** — instale só se você trabalha com interface:

```
/plugin install forge-frontend@forge
```

Ele traz as 10 skills de frontend usadas pelo `dev` (TypeScript, React, Tailwind,
responsividade, dark mode, design de UI). Quem trabalha com MCP, CLI, dados ou infraestrutura
não precisa — e não paga o contexto delas. Se ele não estiver instalado e um briefing nomear
uma dessas skills, a ferramenta responde `Unknown skill: <nome>` e **o trabalho segue**; não é
erro.

### 2. Preparar o repositório (uma vez por repositório)

```
/forge:setup
```

Ele diagnostica a pasta, **mostra o que pretende gravar** e só escreve depois que você
confirmar — nunca sobrescreve nada em silêncio. Se a pasta ainda não for uma "fábrica" (veja a
seção seguinte), ele oferece criar uma. E oferece instalar o `rtk`, que é opcional.

Este passo é necessário porque duas coisas **não viajam dentro de um plugin**:

- as `permissions` (`allow`/`ask`/`deny` de `.claude/settings.json`) — é ali que fica a rede
  de segurança que impede `cdk deploy`, `terraform apply`, `docker push` e comando `aws`
  destrutivo por iniciativa própria de um agente;
- os invariantes, que vão para o `CLAUDE.md` entre marcadores (rodar de novo atualiza, não
  duplica).

### 3. Conferir

```
/forge:doctor
```

Diagnostica e explica o que encontrou, sem alterar nada: contexto detectado, permissions,
invariantes, hooks, `rtk`, uma demonstração inofensiva do guardrail de AWS, e se o `tester`
enxerga o navegador.

### 4. Usar

```
/forge:forge
```

Passo a passo de uso, com exemplos de pedido real em cada fluxo:
[`docs/tutorial.md`](docs/tutorial.md).

## Os dois jeitos de usar

- **Fábrica** — uma pasta base com `projects/` dentro. Todo repositório em que você trabalha é
  clonado para lá, e você conversa sempre com **um** orquestrador rodando na raiz da base, que
  sabe onde cada projeto está. Projeto novo nasce em `projects/<nome>/`, com git próprio. O
  `/forge:setup` cria essa pasta para quem ainda não tem.
- **Repo atual** — o plugin instalado e `/forge` rodado direto dentro do repositório onde você
  já trabalha; o controle fica em `.forge/` na raiz dele.

O hook detecta o contexto sozinho, sem você precisar avisar: é **fábrica** quando a raiz do
repositório tem `projects/` **e** `templates/prompt.template.md`; qualquer outro caso é
**repo atual**.

> ⚠️ **Abra a sessão sempre na raiz** — da fábrica, ou do repositório preparado pelo
> `/forge:setup`. **Nunca abra o Claude Code direto dentro de `projects/<nome>/`** (um
> projeto filho, com git próprio, dentro da fábrica): esse diretório não tem o `CLAUDE.md`
> nem as `permissions` do Forge, e não há garantia de que os hooks do plugin disparem ali —
> a rede de segurança inteira (bloqueio de código pelo orquestrador, guardrail de `aws`
> destrutivo, teto de turnos) depende de rodar a partir da raiz. Se precisar mexer num
> projeto específico, peça ao orquestrador na raiz da fábrica — ele sabe onde cada um está.

## Comandos

- `/forge` — hub do Forge: cria um projeto do zero ou entra no modo fix de um projeto
  existente.
- `/forge:new` — atalho que entra direto no fluxo de criar um projeto do zero.
- `/forge:fix` — atalho que entra direto no modo fix/implementação de um projeto existente.
- `/forge:setup` — prepara o repositório atual para rodar o Forge: grava as `permissions`
  (allow/ask/deny) em `.claude/settings.json` e os invariantes no `CLAUDE.md`; opcionalmente
  cria a fábrica de projetos e/ou instala o `rtk`.
- `/forge:doctor` — diagnostica o ambiente e explica o que encontrou, sem alterar nada:
  contexto detectado, `permissions`, invariantes, hooks, `rtk`, uma demonstração inofensiva
  do guardrail de AWS, e se o `tester` enxerga as ferramentas do navegador.

Passo a passo prático de uso, com exemplos: [`docs/tutorial.md`](docs/tutorial.md).

## Custo e limites

Cada invocação de subagente tem um teto de chamadas de ferramenta, imposto por hook
(`plugins/forge/hooks/subagent-turn-budget.sh`), calibrado pela **mediana** de chamadas que
cada papel gastava nos transcritos medidos — um teto abaixo da mediana estrangula o agente e
gera retrabalho, que é o desperdício mais caro que existe:

| Papel | Aviso | Teto | Variáveis de ambiente | Mediana medida |
|---|---|---|---|---|
| `dev` | 25 | 35 (≈60 turnos) | `FORGE_TURN_WARN` / `FORGE_TURN_CAP` | 42 chamadas (74 turnos) |
| `tester` | 45 | 65 | `FORGE_TESTER_WARN` / `FORGE_TESTER_CAP` | 54 chamadas |
| `scout` | 28 | 40 | `FORGE_SCOUT_WARN` / `FORGE_SCOUT_CAP` | 6 chamadas |

O teto do `dev` é o ponto conservador de propósito: 35 chamadas atingem ~54% das invocações e
respondem por ~58% da conta de subagentes pela simulação (apertar para 26 chegaria a ~76%, mas
corta acima da mediana e o retrabalho de tarefa partida no meio custa mais que a economia). No
teto, a invocação devolve `status: "PARCIAL"` e o orquestrador re-loteia sem perder o trabalho
já feito — não é falha.

Por trás desses tetos está o mesmo custo que justifica a decomposição em tarefas pequenas:

| Turnos na invocação | Custo médio | Custo por turno |
|---|---|---|
| 1–10 | US$ 0,08 | US$ 0,0139 |
| 31–60 | US$ 1,86 | US$ 0,0435 |
| 61–120 | US$ 5,97 | US$ 0,0724 |
| 121+ | US$ 21,93 | US$ 0,1205 |

A coluna da direita é a que importa: não é só a invocação longa que custa mais no total — cada
turno dela custa mais, porque carrega mais contexto.

O `rtk` (Rust Token Killer) é **opcional** — os hooks degradam em silêncio se o binário não
estiver instalado, e nada quebra. Seja honesto sobre o ganho: no perfil de comandos medido
neste repositório ele cortou **~4,5%** do volume de Bash, longe dos "60–90%" anunciados pela
ferramenta. O ganho maior vem das regras de briefing dos próprios agentes (usar
`Grep`/`Glob`/`Read` em vez de `grep`/`find`/`cat`, filtrar na fonte), não do proxy.

## Desenvolvimento

Para rodar os testes do hook que decide quando o `tester` é obrigatório:

```bash
python3 plugins/forge/hooks/tests/test_require_tester.py
```

Além dos testes de hook, o plugin traz uma suíte de avaliação de **comportamento** em `plugins/forge/evals/` — três casos que verificam o que instrução em markdown não consegue garantir sozinha: que um pedido de comando AWS destrutivo não é executado, que a conta é confirmada antes de agir, e que uma investigação não vira loop de escrever código. Rode com `claude plugin eval` (custa tokens: cada caso é uma execução de modelo). `claude plugin validate .` faz a checagem estática de schema, sem custo.

São 15 casos, cada um construído a partir de um payload real de `PostToolUse` capturado na
CLI, com o miolo (`subagent_type` e o texto de retorno do `dev`) trocado por cenário.

O histórico de decisões e as medições que originaram esta ferramenta — os 35 transcritos
analisados, a simulação de custo por teto de turno, os experimentos de paralelismo — vivem no
repositório de origem, `forge-claude`.

## O que ainda não foi verificado

O `tester` em modo `browser` declara as ferramentas do `claude-in-chrome` numa lista restrita
de `tools` no frontmatter do agente. Isso **ainda não foi provado em execução**. Se você
invocar o `tester` em modo `browser` e ele reportar que não enxerga nenhuma ferramenta
`mcp__claude-in-chrome__*`, a correção documentada é: omita o campo `tools` inteiro do
frontmatter de `plugins/forge/agents/tester.md` — sem ele, o subagente herda todas as
ferramentas da sessão, incluindo as do MCP.
