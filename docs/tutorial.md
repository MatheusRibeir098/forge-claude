# Tutorial — usando o Forge no dia a dia

Este é o passo a passo prático. Para entender *por que* a ferramenta é assim, veja o
`README.md` e o `docs/forge-para-a-equipe.md`.

## 1. Instalar (uma vez por máquina)

Dentro do Claude Code:

```
/plugin marketplace add MatheusRibeir098/forge-claude
/plugin install forge@forge-claude
/plugin install forge-frontend@forge-claude     # só se você trabalha com interface
```

O `forge-frontend` traz 10 skills de UI (React, Tailwind, responsividade, dark mode…). Quem
trabalha com MCP, CLI, dados ou infraestrutura não precisa — e não paga o contexto delas.

## 2. Preparar (uma vez por repositório)

```
/forge:setup
```

Ele diagnostica, **mostra o que pretende gravar** e só escreve depois que você confirmar.
Grava duas coisas que não viajam dentro de um plugin:

- as `permissions` em `.claude/settings.json`: `allow` para leitura e ferramentas de baixo
  risco, `ask` para `git push` e `rm -r` (pedem confirmação) e `deny` para `git push` forçado;
- os invariantes no `CLAUDE.md`, entre marcadores, para rodar de novo atualizar em vez de
  duplicar. É ali que vive a regra de nunca fazer deploy nem `push` por iniciativa própria.

Se você ainda não tem uma **fábrica** (uma pasta base onde seus projetos moram), ele oferece
criar. Oferece instalar o `rtk`, que é opcional. E **pergunta** se você quer criar um mapa
local de credenciais (veja a seção 6).

```
/forge:doctor
```

Confere se está tudo de pé: contexto detectado, permissions, invariantes, hooks, `rtk` e se o `tester` enxerga o navegador. Só lê — não altera nada.

## 3. Os dois jeitos de trabalhar

**Fábrica** — você mantém uma pasta base, clona para dentro dela os repositórios em que
trabalha, e conversa sempre com **um** orquestrador na raiz, que sabe onde cada projeto está.
Projeto novo nasce em `projects/<nome>/`, com git próprio.

**Repo atual** — você abre o Claude dentro do repositório onde já trabalha e roda `/forge`.
O controle fica em `.forge/` na raiz dele.

O hook detecta sozinho: se a raiz tem `projects/` e `templates/prompt.template.md`, é fábrica.

> ⚠️ Na fábrica, abra a sessão **sempre na raiz da base**. Nunca abra direto dentro de
> `projects/<nome>/` — é um repositório git separado, sem o `CLAUDE.md` da fábrica, e a
> rede de segurança do Forge (bloqueio de código, teto de turnos) não tem
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

Você pode pular o menu descrevendo direto o que quer, ou usar os atalhos `/forge:new <ideia>`
(fluxo 1) e `/forge:fix <projeto + pedido>` (fluxo 2).

### Fluxo 1 — criar do zero

> *"Quero um painel interno que mostre os chamados abertos por técnico, lendo de uma API
> REST, com filtro por período."*

O Forge faz perguntas (no máximo quatro rodadas), escreve a spec em `prompt.md`, **mostra
para você confirmar**, monta o backlog em `.forge/tasks.md` e começa a despachar `dev` em
paralelo. Cada tarefa com interface passa pelo `tester` antes de ser marcada como pronta.

### Fluxo 2 — fix/implementação

> *"O filtro de data do dashboard está trazendo o mês errado quando o usuário escolhe
> 'últimos 30 dias'."*

Ele invoca um `scout` para entender a estrutura (em vez de abrir os arquivos no contexto
dele), transforma em tarefas e entra no mesmo loop.

### Fluxo 3 — investigar (não termina em código)

> *"O job `sync-pagamentos` começou a falhar ontem à noite. O que aconteceu?"*

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

## 6. Credenciais e ambientes

Ao rodar `/forge:setup`, o Forge **pergunta** se você quer um mapa local de credenciais em
`~/.claude/skills/credenciais-ambiente/SKILL.md`. É opcional, e fica só na sua máquina, fora
do repositório. Se você disser não, o passo é pulado. Se disser sim, ele pergunta o que você
quer catalogar, infere o que der sem tocar em segredo (por exemplo, `gh auth status`), e
pergunta o resto: para que serve cada item, onde a credencial vive, como renovar e se é
produção, administrativa, de terceiro ou proibida para agente. O mapa serve para o agente
saber **qual conta usar**: perfis de nuvem de qualquer provedor, contas do `gh`, tokens de
API, service accounts e bancos.

Regra do mapa: **só ponteiros, nunca o segredo.** Escreva o nome do perfil, a variável de
ambiente ou o caminho do arquivo de credencial, e nunca o valor da chave ou do token.

Quanto a ações irreversíveis, a regra é uma só: **nunca `git push` nem deploy sem ordem
explícita sua.** O agente descreve a ação e devolve para você executar.

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

Para medir o seu próprio uso, no repositório onde o Forge foi usado (o script fica em
`plugins/forge/bin/forge-tokens` neste marketplace):

```
forge-tokens --desde AAAA-MM-DD
```

Compare com `docs/linha-de-base.md`.

## 8. Quando algo não funciona

| sintoma | o que é |
|---|---|
| o `tester` diz que não enxerga o navegador | rode `/forge:doctor`, que diagnostica e diz a correção |
| um push ou deploy foi recusado | é a regra de ação irreversível. Ele descreve a ação: execute você mesmo se for mesmo o que você quer |
| ele parou e perguntou | Loop Travado — três tentativas no mesmo erro. Responda com a informação que falta |
| prompt de permissão em todo comando | faltou `/forge:setup` neste repositório |
| o `tester` nunca é invocado | verifique se a tarefa tem interface ou superfície verificável; tarefa de refactor puro não precisa |
| o agente saiu da pasta do projeto | veja abaixo |

### O agente saiu da pasta do projeto

A pasta de trabalho do shell persiste entre chamadas de `Bash`. Se o orquestrador roda um
`cd /outra/pasta` solto para ler algo e não volta, as chamadas seguintes ficam fora da raiz,
onde as regras e os arquivos de `.claude/` da pasta base deixam de valer. O hook
`volta-pasta-base.py` cobre isso na sessão principal: quando a pasta do shell diverge de
`CLAUDE_PROJECT_DIR`, ele reescreve o comando como `cd "<raiz>" && <comando>` e mostra um
aviso começando com `[pasta base]`. Não precisa fazer nada. Ele não decide permissões (isso
continua com as `permissions`) e, se algo estranho acontecer, deixa o comando passar
intacto. O aviso é só um lembrete para o agente usar `cd x && cmd` ou caminhos absolutos.

Isso não vale para uma sessão **aberta** dentro de `projects/<nome>/`: ali a raiz do projeto
já é a pasta errada. Feche e reabra na raiz da fábrica.
