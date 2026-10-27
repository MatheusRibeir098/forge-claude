# Forge para a equipe: o que é, por que existe e como adotar

## Resumo executivo

O Forge é um plugin do Claude Code que organiza o trabalho de agente de IA em quatro papéis fixos — orquestrador, `dev`, `tester` e `scout` — com a divisão imposta por hook, não por instrução que o modelo possa ignorar. A tese central: as invocações longas tendem a concentrar uma parte desproporcional do custo, porque o contexto de um agente é reenviado inteiro a cada turno — o mesmo turno custa mais numa invocação longa do que numa curta. O plugin embute limites que atacam esse ponto, skills de guardrail para ambiente real, e um mecanismo de distribuição: quem publica uma melhoria atualiza a ferramenta de toda a equipe. Este documento reúne o problema, o mecanismo que o resolve em parte, o que a ferramenta cobre além de criar projeto, e o que ainda não está comprovado.

## O problema

O custo de uma invocação cresce mais que proporcionalmente à duração: o contexto é reenviado inteiro a cada turno e só cresce, nunca é podado. O mesmo turno custa mais no fim de uma invocação longa do que numa curta, então poucas invocações muito longas podem concentrar boa parte do custo de subagentes. A causa não é volume de trabalho, é contexto reenviado: o grosso do gasto tende a aparecer como `cache_read` (você confere isso no seu próprio uso com o `forge-tokens`). E a sessão principal pode custar mais que todos os subagentes somados — é ela que acumula varredura e nunca poda, o que justifica um papel dedicado a ler em contexto descartável.

Dentro de cada invocação, a saída de `Bash` pode dominar o que o subagente ingere: um `cat` traz mais caracteres que uma busca equivalente, e ler o arquivo inteiro quando só uma parte interessa paga o excesso em todo turno seguinte. Um compressor de saída como o `rtk` ajuda, mas sozinho não resolve o problema de fundo, que é o contexto crescer.

Os números variam por pessoa e por projeto. **Meça a sua:** [`docs/linha-de-base.md`](linha-de-base.md) explica como rodar `plugins/forge/bin/forge-tokens` e comparar antes e depois.

Dado externo: 93% das organizações já tiveram ao menos um incidente de infraestrutura causado por IA, e só 19% têm governança preparada para o próximo (fonte: relatório "State of Infrastructure Automation 2026", da Spacelift, citado em bex.co/blog/2026/07/11/vibe-coding-incident-guardrails). O Forge não elimina esse risco, mas ataca as duas causas mais controláveis: agente sem teto que foge de controle, e agente sem barreira que toca produção sem checagem.

## O que é a ferramenta

O Forge é um plugin do Claude Code publicado em `github.com/MatheusRibeir098/forge-claude`. O usuário conversa com **um orquestrador único**, que levanta requisitos, monta a especificação, quebra o trabalho em tarefas atômicas e despacha subagentes — em paralelo, quando possível.

## Como funciona: os papéis e os hooks que os impõem

- **`dev`** (sonnet) escreve todo o código de produto — é o único papel que pode fazer isso.
- **`tester`** (sonnet) valida se o que o `dev` entregou funciona, e emite o veredito final (`PASSOU`/`FALHOU`). Não escreve código de produto.
- **`scout`** (haiku, mais barato) lê, varre e pesquisa em volume. A varredura fica no contexto dele e morre quando ele termina — só o resumo volta ao orquestrador.

O ponto central do desenho é que essa divisão é **imposta por hook**, não por instrução de prompt que o modelo pode esquecer numa conversa longa. Um hook bloqueia o orquestrador de escrever código de produto; outro bloqueia o `dev` de validar a própria entrega (subir servidor, rodar navegador/E2E, print, HTTP); um terceiro conta as chamadas de ferramenta de cada invocação e aplica um teto por papel, ajustável por variável de ambiente. Outros dois cuidam do contexto do orquestrador: um lembra de delegar ao `scout` quando ele emenda leituras em vez de delegar, e outro devolve o shell da sessão principal à pasta base do projeto quando um `cd` solto o deixa para fora. Por fim, um hook decide, ao fim de cada `dev`, se o `tester` é obrigatório e em que modo; ele também guarda a pendência de validação e trata os vereditos do `tester`. No teto, a invocação devolve só em texto o trabalho já feito (`PARCIAL` no `dev` e no `scout`; veredito no `tester`), e o orquestrador re-lotea o restante em vez de reiniciar a tarefa. Prompt é sugestão; hook é regra que se aplica mesmo quando o modelo "decidiria" diferente.

O `tester` opera em dois modos: `browser` (Chrome real do usuário, sempre serial, teto de evidências por tarefa) e `contrato` (sem navegador: sobe o servidor MCP, chama as ferramentas com payload real, roda a suíte de teste do pacote tocado, e confere infraestrutura **só por leitura** — nunca comandos que criam, alteram, apagam ou fazem deploy).

## O que muda no dia a dia

Quem hoje conversa direto com um agente genérico perde tempo repetindo contexto, corrigindo o agente quando ele valida a própria mudança, ou descobrindo tarde que uma investigação consumiu contexto enorme sem necessidade. Com o Forge: descrever o objetivo ao orquestrador, receber tarefas decompostas, ver `dev` e `tester` trabalharem em paralelo dentro de limites, revisar o que voltou — sem abrir terminal de agente. Serve tanto para construir um projeto do zero quanto para consertar um já existente.

## Governança e segurança

Quando o trabalho técnico acontece em ambiente real, o risco citado acima (93% das organizações com incidente causado por IA) é diretamente relevante. O plugin traz skills e regras de guardrail que carregam sozinhas quando a tarefa é desse tipo:

- **Identidade antes de agir** — conferir em qual conta, perfil ou ambiente o comando vai rodar antes de prosseguir. O `/forge:setup` pergunta se você quer um mapa local de credenciais (`~/.claude/skills/credenciais-ambiente/SKILL.md`), só com ponteiros, nunca o segredo.
- **Leitura separada de mutação e destrutivo** — exploração nunca justifica escrita; ação que cria, altera ou apaga recurso exige pedido explícito.
- **Nunca push nem deploy sem ordem explícita** — a regra é genérica e vale para qualquer provedor; `docker push` e afins não rodam por iniciativa própria.
- **Diff de infraestrutura lido com critério** — permissão mais ampla, recurso com estado sem retenção, exposição pública nova.
- **Leitura de banco read-only**, `LIMIT` em exploração, cuidado com PII em log/relatório.

## Distribuição para a equipe

Hoje, quando alguém descobre uma boa prática — um jeito mais seguro de rodar uma query pesada, um checklist que evita erro de permissão — ela fica na máquina dessa pessoa, sem virar hábito do resto do time. Publicada como skill do Forge, ela vira comportamento que a ferramenta aplica: quem faz o push atualiza a ferramenta de todo mundo. O repositório distribui dois plugins por esse mecanismo — `forge` (orquestrador e os três papéis) e `forge-frontend` (skills de frontend do `dev`) — no mesmo marketplace.

## Serve para qualquer trabalho, não só criar projeto

O mesmo mecanismo atende investigação de incidente, leitura de banco, automação, análise de custo e revisão de infraestrutura. Nesses casos o `scout` vira o papel principal: várias instâncias rodam na mesma mensagem sem colidir (é tudo leitura), cruzando sinais de fontes diferentes (log, métrica, código, custo, infraestrutura) e devolvendo relatório — sem forçar o loop de "escrever código" quando a tarefa era só entender o que aconteceu.

## Evidências e métricas

Subagente sem modelo explícito herda o modelo do orquestrador, e um modelo maior encarece a invocação — por isso `dev` e `tester` ficam fixos em sonnet. O `dev` concentra o trabalho e, em geral, o custo; `tester` e `scout` custam menos por invocação. Quanto ao teto de turnos, as invocações que passam do teto do próprio papel são exatamente as que o hook passa a cortar; quantas são, e quanto isso economiza, depende do seu uso: meça com [`docs/linha-de-base.md`](linha-de-base.md).

Há um teto por papel: `dev` avisa em 25 e corta em 35, `tester` avisa em 45 e corta em 65 (precisa de mais fôlego porque sobe servidor e valida), `scout` avisa em 28 e corta em 40; agentes genéricos (`general-purpose`, `Explore`, agentes de outros plugins) avisam em 30 e cortam em 40, e no teto devolvem `status: "PARCIAL"`. Cada um é ajustável por variável de ambiente (`FORGE_TURN_CAP`, `FORGE_TESTER_CAP`, `FORGE_SCOUT_CAP`, `FORGE_OUTRO_CAP`) — quem achar o teto apertado para o próprio trabalho muda sem tocar no plugin.

## O que ainda não está provado

- Não há medição própria neste repositório. O ganho do teto de turnos e dos demais hooks só está provado na sua máquina depois que você medir antes e depois (veja [`docs/linha-de-base.md`](linha-de-base.md)).
- A economia do teto depende de premissa: que a tarefa re-loteada no teto cabe em poucos lotes. Se cada tarefa longa virar muitos lotes, o ganho cai. O princípio é cortar as invocações que fogem de controle, não espremer as normais.
- O `tester` em modo `browser` depende de ferramentas que vêm de um servidor MCP. O plugin usa o único caminho que a documentação oficial garante — o agente não declara `tools`, e assim herda as ferramentas MCP da sessão. Falta confirmar em uso real que isso entrega o navegador a ele; o comando `/forge:doctor` faz essa verificação e diz o que fazer em cada desfecho. Enquanto não for confirmado, o modo `contrato` (sem navegador) funciona normalmente.
- A suíte de avaliação automatizada do plugin ainda é mínima: `plugins/forge/evals/` tem 1 caso (`investigacao-nao-vira-codigo`, com `prompt.md` e 3 graders). Os hooks têm 7 scripts de teste unitário (`test_delega_varredura.py`, `test_deny_bash_writes.py`, `test_deny_orchestrator.py`, `test_identidade_local.py`, `test_require_tester.py`, `test_subagent_turn_budget.py` e `test_volta_pasta_base.py`), com 92 casos no total.

## Como adotar

1. `/plugin marketplace add MatheusRibeir098/forge-claude`
2. `/plugin install forge@forge-claude`
3. Opcional, para quem trabalha com interface: `/plugin install forge-frontend@forge-claude`
4. No repositório de trabalho, rodar `/forge:setup` — grava as permissões (`git push` pede confirmação, push forçado é negado) e os invariantes do `CLAUDE.md` — incluindo a regra de nunca fazer deploy nem push sem ordem explícita —, que não viajam dentro de um plugin. O comando mostra o que vai gravar, pede confirmação, e pergunta se você quer o mapa local de credenciais.
5. A partir daí: `/forge` (cria projeto ou entra em modo de conserto), ou os atalhos `/forge:new` e `/forge:fix`.

## Glossário

- **Orquestrador** — sessão principal, com quem o usuário conversa; decompõe tarefas e despacha subagentes, mas não escreve código.
- **Subagente** — invocação isolada (`dev`, `tester`, `scout`) com contexto próprio, que devolve resultado estruturado.
- **Skill** — instruções carregadas sob demanda quando a tarefa se encaixa nelas.
- **Hook** — script que o Claude Code executa em pontos fixos do ciclo, capaz de bloquear ou modificar uma ação — mecanismo, não instrução que o modelo possa ignorar.
- **Plugin** — pacote instalável de agentes, skills, hooks e comandos, distribuído por marketplace.
- **Turno** — uma rodada de interação dentro de uma invocação; unidade que mais pesa no custo.
- **Contexto** — histórico de uma invocação, reenviado ao modelo a cada turno seguinte.
