# Linha de base — meça o seu consumo antes e depois

Este repositório não traz uma medição pronta: o consumo depende de quem usa, do projeto e do
tipo de tarefa. O que ele traz é a régua, `plugins/forge/bin/forge-tokens`, que lê os
transcripts do Claude Code do seu próprio projeto e mostra onde o token foi gasto. O fluxo é
simples: meça **antes** de adotar o Forge (ou antes de mudar uma configuração), use por um
tempo, meça de novo com a mesma régua e compare.

## O que rodar

O script não tem dependências além do Python 3. Rode-o de dentro do projeto que você quer medir:

```
cd <projeto onde o Forge foi usado>
<caminho-do-plugin>/bin/forge-tokens --desde AAAA-MM-DD
```

Flags reais:

| flag | efeito |
|---|---|
| (nenhuma) | mede o projeto do diretório atual, desde o início do histórico |
| `--desde AAAA-MM-DD` | só conta turnos a partir da data (aceita data ou timestamp ISO) |
| `--dir <caminho>` | mede o projeto de outro diretório |
| `--projeto <slug>` | usa um slug explícito de `~/.claude/projects/<slug>`; aceita slug que começa com `-` (`-home-fulano-app`) |
| `--json` | saída em JSON, útil para guardar e comparar por script |

O slug do projeto é derivado do caminho absoluto (com `/` trocado por `-`), o mesmo critério
que o Claude Code usa para nomear `~/.claude/projects/<slug>`. Os transcripts de subagente
ficam em `<sessão>/subagents/*.jsonl`; o script já caminha por essa árvore.

Para guardar a medição de hoje e comparar depois:

```
forge-tokens --desde AAAA-MM-DD --json > linha-de-base-antes.json
```

## O que cada métrica significa

Os valores abaixo são **fictícios**, só para mostrar o formato da saída:

```
sessões: 10   invocações de subagente: 100   turnos totais: 3.000
tokens de entrada (com cache): 300.000.000   tokens de saída: 1.000.000

                       custo      %   turnos     cache_read   cache_write
sessão              US$ 100,00    50%   1.000    ...
subagentes          US$ 100,00    50%   2.000    ...
TOTAL               US$ 200,00
```

- **sessões e invocações**: quantas conversas principais e quantas invocações de subagente
  entraram no período.
- **turnos**: respostas do modelo, deduplicadas por `message.id`. O Claude Code grava a mesma
  mensagem em mais de uma linha do `.jsonl`; sem deduplicar, os turnos e o custo saem
  inflados. O script já faz isso.
- **tokens de entrada (com cache)**: soma de entrada normal, leitura de cache e escrita de
  cache. Quase sempre domina a conta, porque o contexto é reenviado a cada turno.
- **custo**: a preço de lista da API, por família de modelo, com cache lido a 0,1x e escrito a
  1,25x (TTL de 5 min) ou 2x (TTL de 1 h). Num plano de assinatura você não paga esse valor;
  use-o para comparar as partes entre si, não como fatura.
- **sessão × subagentes**: quanto da conta fica na conversa principal e quanto vai para os
  subagentes. A sessão principal acumula tudo o que lê e nunca poda; é o que o `scout` existe
  para aliviar.
- **por tipo de subagente**: custo, invocações, custo por invocação e turnos por invocação de
  cada papel (`dev`, `scout`, `tester`, outros).
- **`>teto` e "invocações acima do teto do próprio papel"**: quantas invocações passaram do
  teto de turnos do papel. O teto do hook é em chamadas de ferramenta; o script converte para
  turnos com ~1,73 turno por chamada, então é uma estimativa, não leitura direta. O hook
  devolve `PARCIAL` nesse ponto.
- **faixas de turnos** (1-10, 11-30, 31-60, 61-120, 121+): quantas invocações caem em cada
  faixa, com custo por invocação e **custo por turno**. É a alavanca principal. Como o
  contexto cresce a cada turno, o mesmo turno custa mais numa invocação longa do que numa
  curta, e poucas invocações longas podem concentrar boa parte do custo de subagentes.
- **turnos do `dev`**: mediana, p90 e máximo, mais o teto do hook para o papel.

## Como comparar antes e depois

Use a mesma data de corte em período de duração parecida (por exemplo, 30 dias antes e 30
dias depois de adotar) e olhe, em ordem de importância:

1. **A distribuição por faixa de turnos.** É onde o teto aparece primeiro. Se ele estiver
   funcionando, as faixas 61-120 e 121+ encolhem e a 31-60 engorda: mesmo trabalho, contexto
   começando limpo mais vezes.
2. **Invocações acima do teto do próprio papel.** A linha deve cair para perto de zero depois
   que o hook passa a cortar.
3. **Custo por turno na faixa alta.** É a métrica menos sujeita a variação do volume de
   trabalho.
4. **A proporção sessão × subagentes.** Se a sessão principal pesa mais que todos os
   subagentes somados, há varredura acumulando no contexto que é reenviado a cada turno; é o
   que o `scout` ataca.

## Ressalvas

1. **Uma medição antes/depois não é um experimento controlado.** O volume e o tipo de
   trabalho mudam entre períodos; prefira métricas por turno e por faixa a totais absolutos.
2. **Amostra pequena engana.** Poucas sessões ou poucos dias deixam as faixas altas com um ou
   dois casos; amplie o período antes de concluir.
3. **O teto não corta trabalho, redistribui.** Uma tarefa cortada no teto volta como
   `PARCIAL` e vira mais de um lote. O ganho vem de cortar a invocação que foge de controle,
   não de espremer as normais; se cada tarefa longa virar vários lotes, a economia é menor do
   que parece.
4. **Os tetos por papel do script são cópias dos do hook** (`subagent-turn-budget.sh`). Se
   você mudar os tetos por variável de ambiente (`FORGE_TURN_CAP`, `FORGE_TESTER_CAP`,
   `FORGE_SCOUT_CAP`, `FORGE_OUTRO_CAP`), a coluna `>teto` continua usando os valores padrão.
