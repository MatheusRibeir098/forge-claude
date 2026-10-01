# Tutorial — usando o Forge no dia a dia

Este é o passo a passo prático. Para entender *por que* a ferramenta é assim, veja o
`README.md` e o `docs/forge-para-a-equipe.md`.

## 1. Instalar (uma vez por máquina)

Dentro do Claude Code:

```
/plugin marketplace add datisolucoesemti/dati-forge-plugin
/plugin install forge@forge
/plugin install forge-frontend@forge     # só se você trabalha com interface
```

O `forge-frontend` traz 10 skills de UI (React, Tailwind, responsividade, dark mode…). Quem
trabalha com MCP, CLI, dados ou infraestrutura não precisa — e não paga o contexto delas.

## 2. Preparar (uma vez por repositório)

```
/forge:setup
```

Ele diagnostica, **mostra o que pretende gravar** e só escreve depois que você confirmar.
Grava duas coisas que não viajam dentro de um plugin:

- as `permissions` em `.claude/settings.json` — inclusive o `deny` que impede `cdk deploy`,
  `terraform apply` e comando `aws` destrutivo;
- os invariantes no `CLAUDE.md`, entre marcadores, para rodar de novo atualizar em vez de
  duplicar.

Se você ainda não tem uma **fábrica** (uma pasta base onde seus projetos moram), ele oferece
criar. E oferece instalar o `rtk`, que é opcional.

```
/forge:doctor
```

Confere se está tudo de pé: contexto detectado, permissions, invariantes, hooks, `rtk`, o
guardrail de AWS e se o `tester` enxerga o navegador. Só lê — não altera nada.

## 3. Os dois jeitos de trabalhar

**Fábrica** — você mantém uma pasta base, clona para dentro dela os repositórios em que
trabalha, e conversa sempre com **um** orquestrador na raiz, que sabe onde cada projeto está.
Projeto novo nasce em `projects/<nome>/`, com git próprio.

**Repo atual** — você abre o Claude dentro do repositório onde já trabalha e roda `/forge`.
O controle fica em `.forge/` na raiz dele.

O hook detecta sozinho: se a raiz tem `projects/` e `templates/prompt.template.md`, é fábrica.

> ⚠️ Na fábrica, abra a sessão **sempre na raiz da base**. Nunca abra direto dentro de
> `projects/<nome>/` — é um repositório git separado, sem o `CLAUDE.md` da fábrica, e a
> rede de segurança do Forge (bloqueio de código, guardrail de AWS, teto de turnos) não tem
> garantia de valer ali. Precisa mexer num projeto? Peça ao orquestrador rodando na raiz.

## 4. Os três fluxos

```
/forge
```

```
1. 🆕 Criar um projeto do zero
2. 🔧 Fix/implementação em projeto existente
3. 🔎 Investigar/Analisar — incidente, banco, custo, infraestrutura
```

Você pode pular o menu descrevendo direto o que quer.

### Fluxo 1 — criar do zero

> *"Quero um painel interno que mostre os chamados abertos do Tiflux por técnico, com filtro
> por período."*

O Forge faz perguntas (no máximo quatro rodadas), escreve a spec em `prompt.md`, **mostra
para você confirmar**, monta o backlog em `.forge/tasks.md` e começa a despachar `dev` em
paralelo. Cada tarefa com interface passa pelo `tester` antes de ser marcada como pronta.

### Fluxo 2 — fix/implementação

> *"O filtro de data do dashboard está trazendo o mês errado quando o usuário escolhe
> 'últimos 30 dias'."*

Ele invoca um `scout` para entender a estrutura (em vez de abrir os arquivos no contexto
dele), transforma em tarefas e entra no mesmo loop.

### Fluxo 3 — investigar (não termina em código)

> *"A Lambda `process-payment-webhook` começou a falhar ontem à noite. O que aconteceu?"*

Este é **read-only**. O `scout` é o protagonista, a entrega é um relatório em
`.forge/investigacao-<data>.md`, e só vira trabalho de código se você pedir **depois** de ler
o relatório. Serve para incidente, análise de custo, revisão de infraestrutura e leitura de
banco.

## 5. O que esperar durante o trabalho

- **Você fala só com o orquestrador.** Nunca precisa abrir terminal de agente nem falar com
  subagente.
- **Ele paraleliza sozinho.** Tarefas independentes vão na mesma mensagem. Se você precisou
  pedir "adianta outra coisa junto", ele falhou nisso.
- **Ele decide validar e avisa** — não pergunta. Você recebe uma linha dizendo o que vai ser
  validado e por quê.
- **`PARCIAL` não é erro.** Quando um `dev` bate no teto de turnos, ele devolve o que fez e o
  Forge re-loteia o resto. É o caminho esperado para tarefa grande.
- **Loop Travado:** o mesmo erro três vezes → ele reformula; se persistir, **para e te
  pergunta** em vez de insistir.

## 6. Trabalhando com AWS

Antes do primeiro comando que toca uma conta, o Forge confirma **onde está**
(`aws sts get-caller-identity`) e te diz conta, perfil e região. Se for produção, ele fala
isso em voz alta.

Três camadas de proteção, e vale saber que existem:

| | |
|---|---|
| leitura (`describe-*`, `list-*`, `get-*`) | livre |
| mutação reversível (`create-*`, `update-*`) | pede confirmação |
| destrutivo (`delete-*`, `s3 rm`, `terminate-*`, e tudo que altera IAM) | **bloqueado** — ele descreve a ação e devolve para você executar |

O bloqueio é um hook que lê o comando de verdade: `aws --profile prod s3 rm` é barrado mesmo
com a flag antes do serviço, e a mensagem cita o profile para você ver em qual conta quase
mexeu.

## 7. Custo — o que você controla

O gasto dominante é **turno dentro de uma invocação**, porque o contexto é reenviado inteiro a
cada turno. Três coisas que ajudam de verdade:

1. **Tarefa bem recortada.** Uma tarefa que cabe em ~35 chamadas de ferramenta custa muito
   menos que uma que fica 150 turnos tentando.
2. **Deixe o `scout` varrer.** Uma varredura no `scout` custa ~US$ 0,08 e é descartada; a
   mesma varredura no contexto principal é recobrada em **todo** turno seguinte. Um hook te
   lembra disso quando você emenda 8 leituras seguidas.
   Regra prática: **no começo de uma sessão longa, delegue; perto do fim, leia direto.**
3. **Sessão nova para assunto novo.** Contexto acumulado é o que encarece — e ele não diminui.

Para medir o seu próprio uso:

```
plugins/forge/bin/forge-tokens --desde AAAA-MM-DD
```

Compare com `docs/linha-de-base.md`.

## 8. Quando algo não funciona

| sintoma | o que é |
|---|---|
| o `tester` diz que não enxerga o navegador | rode `/forge:doctor`, que diagnostica e diz a correção |
| um comando AWS foi recusado | é o guardrail. Ele descreve a ação: execute você mesmo se for mesmo o que você quer |
| ele parou e perguntou | Loop Travado — três tentativas no mesmo erro. Responda com a informação que falta |
| prompt de permissão em todo comando | faltou `/forge:setup` neste repositório |
| o `tester` nunca é invocado | verifique se a tarefa tem interface ou superfície verificável; tarefa de refactor puro não precisa |
