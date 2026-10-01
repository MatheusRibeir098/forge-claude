# Forge para a equipe: o que é, por que existe e como adotar

## Resumo executivo

O Forge é um plugin do Claude Code que organiza o trabalho de agente de IA em três papéis fixos — orquestrador, `dev` e `tester` — com a divisão imposta por hook, não por instrução que o modelo possa ignorar. Medido em 30 dias de uso real: as invocações que passaram de 60 turnos foram 8,8% do total e metade do custo de subagentes, porque o contexto de um agente é reenviado inteiro a cada turno — o mesmo turno custa 8,7 vezes mais numa invocação longa do que numa curta. O plugin embute limites que atacam esse ponto, skills de guardrail para ambiente real, e um mecanismo de distribuição: quem publica uma melhoria atualiza a ferramenta de toda a equipe. Este documento reúne o problema medido, o mecanismo que o resolve em parte, o que a ferramenta cobre além de criar projeto, e o que ainda não está comprovado.

## O problema, com os números

Entre 17 de agosto e 16 de setembro de 2026 (uma pessoa, 43 sessões), o uso do agente somou 328 invocações de subagente e 12.077 turnos, processando 1,49 bilhão de tokens de entrada e 4,08 milhões de saída, a um custo de US$ 901,96. Distribuição por duração: 83 invocações de 1-10 turnos, 140 de 11-30, 76 de 31-60, 27 de 61-120, e 2 acima de 120.

O custo por invocação cresce desproporcional à duração: US$ 0,08 (1-10 turnos), US$ 0,41 (11-30), US$ 1,86 (31-60), US$ 5,97 (61-120), US$ 21,93 (121+) — 274 vezes a faixa mais barata. E o custo por turno acompanha: de US$ 0,0139 na faixa curta para US$ 0,1205 na longa.

O achado central: as 29 invocações que passaram de 60 turnos são 8,8% do total e concentram 50% do custo de subagentes. A causa não é volume de trabalho — é que o contexto de uma invocação é reenviado inteiro a cada turno e só cresce, nunca é podado; por isso o mesmo turno custa 8,7 vezes mais no fim de uma invocação longa. A composição do gasto confirma: quase todo o custo é `cache_read`, ou seja, contexto reenviado. E a sessão principal custou mais que todos os subagentes somados (US$ 492 contra US$ 410) — é ela que acumula varredura e nunca poda, o que explica por que existe um papel dedicado a ler em contexto descartável.

Dentro de cada invocação, `Bash` respondeu por 61% de tudo que os subagentes ingeriram; um `cat` custou em média 3.905 caracteres contra 1.121 de uma busca equivalente; 74% das leituras puxaram o arquivo inteiro sem precisar. O `rtk`, compressor de saída usado como mitigação, corta ~4,5% do volume de `Bash` — longe dos "60–90%" anunciados. Nenhum compressor resolve sozinho o problema de fundo.

Dado externo: 93% das organizações já tiveram ao menos um incidente de infraestrutura causado por IA, e só 19% têm governança preparada para o próximo (fonte: bex.co/blog/2026/07/11/vibe-coding-incident-guardrails). O Forge não elimina esse risco, mas ataca as duas causas mais controláveis: agente sem teto que foge de controle, e agente sem barreira que toca produção sem checagem.

## O que é a ferramenta

O Forge é um plugin do Claude Code publicado em `github.com/MatheusRibeir098/forge-claude`. O usuário conversa com **um orquestrador único**, que levanta requisitos, monta a especificação, quebra o trabalho em tarefas atômicas e despacha subagentes — em paralelo, quando possível.

## Como funciona: os três papéis e os hooks que os impõem

- **`dev`** (sonnet) escreve todo o código de produto — é o único papel que pode fazer isso.
- **`tester`** (sonnet) valida se o que o `dev` entregou funciona, e emite o veredito final (`PASSOU`/`FALHOU`). Não escreve código de produto.
- **`scout`** (haiku, mais barato) lê, varre e pesquisa em volume. A varredura fica no contexto dele e morre quando ele termina — só o resumo volta ao orquestrador.

O ponto central do desenho é que essa divisão é **imposta por hook**, não por instrução de prompt que o modelo pode esquecer numa conversa longa. Um hook bloqueia o orquestrador de escrever código de produto; outro bloqueia o `dev` de validar a própria entrega (subir servidor, rodar navegador/E2E, print, HTTP); um terceiro conta as chamadas de ferramenta de cada invocação e aplica um teto por papel, calibrado pela mediana medida no uso real. No teto, a invocação devolve o trabalho já feito como `PARCIAL`, e o orquestrador re-lotea o restante em vez de reiniciar a tarefa. Prompt é sugestão; hook é regra que se aplica mesmo quando o modelo "decidiria" diferente.

O `tester` opera em dois modos: `browser` (Chrome real do usuário, sempre serial, teto de evidências por tarefa) e `contrato` (sem navegador: sobe o servidor MCP, chama as ferramentas com payload real, roda a suíte de teste do pacote tocado, e confere infraestrutura **só por leitura** — nunca comandos que criam, alteram, apagam ou fazem deploy).

## O que muda no dia a dia

Quem hoje conversa direto com um agente genérico perde tempo repetindo contexto, corrigindo o agente quando ele valida a própria mudança, ou descobrindo tarde que uma investigação consumiu contexto enorme sem necessidade. Com o Forge: descrever o objetivo ao orquestrador, receber tarefas decompostas, ver `dev` e `tester` trabalharem em paralelo dentro de limites, revisar o que voltou — sem abrir terminal de agente. Serve tanto para construir um projeto do zero quanto para consertar um já existente.

## Governança e segurança

A maior parte do trabalho técnico acontece em ambiente real — o que torna o risco citado acima (93% das organizações com incidente causado por IA) diretamente relevante. O plugin traz skills e regras de guardrail que carregam sozinhas quando a tarefa é desse tipo:

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

Além dos números da seção "O problema": `dev` foi invocado 232 vezes (US$ 1,16 por invocação, mediana de 22 turnos, máximo de 169), `scout` 40 (US$ 0,08) e `tester` 25 (US$ 0,38) — o `dev` concentra o trabalho e o custo, enquanto `tester` e `scout` são baratos e subusados. Subagente sem modelo explícito herda o modelo do orquestrador; com opus em vez de sonnet, o custo por invocação foi 2,8 vezes maior — por isso `dev` e `tester` ficam fixos em sonnet. Sobre a conta de US$ 901,96 do período, a projeção de economia do teto de turnos é de US$ 93 — 23% do custo de subagentes, 10% da conta total. E 22 das 328 invocações (7%) passaram do teto do próprio papel: são exatamente as que o hook passa a cortar.

Os tetos são calibrados pela mediana real de chamadas de ferramenta que cada papel gastou, não por número redondo: `dev` avisa em 25 e corta em 35, `tester` avisa em 45 e corta em 65 (precisa de mais fôlego porque sobe servidor e valida), `scout` avisa em 28 e corta em 40. Cada um é ajustável por variável de ambiente (`FORGE_TURN_CAP`, `FORGE_TESTER_CAP`, `FORGE_SCOUT_CAP`) — quem achar o teto apertado para o próprio trabalho muda sem tocar no plugin.

## O que ainda não está provado

- A projeção de economia depende de premissa otimista: que a tarefa re-loteada no teto cabe no número mínimo de lotes. Num cenário pessimista, com cada tarefa longa virando três lotes em vez de dois, a economia cai para perto de 1%. O ganho real está em cortar as invocações que fogem de controle, não em espremer as normais.
- Uma medição anterior deste mesmo período circulou com números inflados: ela contava turnos sem deduplicar por `message.id`, e o Claude Code grava a mesma mensagem várias vezes no transcript (8.883 de 11.859 mensagens aparecem repetidas). O fator era exatamente 2,00x, e a distribuição por faixa saía deslocada para cima. Os números deste documento são os corrigidos, medidos com `plugins/forge/bin/forge-tokens`; a linha de base completa está em `docs/linha-de-base.md`.
- As métricas vêm de uma pessoa só, em 20 dias, e descrevem o comportamento **anterior** às mudanças do plugin — nada foi medido depois do teto de turnos e dos demais hooks em produção.
- O `tester` em modo `browser` depende de ferramentas que vêm de um servidor MCP. O plugin usa o único caminho que a documentação oficial garante — o agente não declara `tools`, e assim herda as ferramentas MCP da sessão. Falta confirmar em uso real que isso entrega o navegador a ele; o comando `/forge:doctor` faz essa verificação e diz o que fazer em cada desfecho. Enquanto não for confirmado, o modo `contrato` (sem navegador) funciona normalmente.
- A suíte de avaliação automatizada do plugin ainda é mínima: `plugins/forge/evals/` tem 1 caso (`investigacao-nao-vira-codigo`, com `prompt.md` e 3 graders). Os hooks têm 4 scripts de teste unitário, com 44 casos no total.

## Como adotar

1. `/plugin marketplace add MatheusRibeir098/forge-claude`
2. `/plugin install forge@forge-claude`
3. Opcional, para quem trabalha com interface: `/plugin install forge-frontend@forge-claude`
4. No repositório de trabalho, rodar `/forge:setup` — grava as permissões (allowlist que bloqueia deploy/push acidental) e os invariantes do `CLAUDE.md`, que não viajam dentro de um plugin.
5. A partir daí: `/forge` (cria projeto ou entra em modo de conserto), ou os atalhos `/forge:new` e `/forge:fix`.

## Glossário

- **Orquestrador** — sessão principal, com quem o usuário conversa; decompõe tarefas e despacha subagentes, mas não escreve código.
- **Subagente** — invocação isolada (`dev`, `tester`, `scout`) com contexto próprio, que devolve resultado estruturado.
- **Skill** — instruções carregadas sob demanda quando a tarefa se encaixa nelas.
- **Hook** — script que o Claude Code executa em pontos fixos do ciclo, capaz de bloquear ou modificar uma ação — mecanismo, não instrução que o modelo possa ignorar.
- **Plugin** — pacote instalável de agentes, skills, hooks e comandos, distribuído por marketplace.
- **Turno** — uma rodada de interação dentro de uma invocação; unidade que mais pesa no custo.
- **Contexto** — histórico de uma invocação, reenviado ao modelo a cada turno seguinte.
