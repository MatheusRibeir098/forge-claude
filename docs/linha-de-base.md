# Linha de base — consumo medido antes das mudanças

Medição feita com `plugins/forge/bin/forge-tokens`, sobre os transcripts reais da
fábrica de onde este plugin foi extraído (a pasta de trabalho do autor). Serve de régua para comparar depois que o plugin
estiver em uso.

```
forge-tokens --desde 2026-08-17
```

## O que foi medido

Período de **17/ago a 16/set de 2026**, **uma pessoa**, 43 sessões.

| | |
|---|---|
| invocações de subagente | 328 |
| turnos | 12.077 |
| tokens de entrada (com cache) | 1,49 bilhão |
| tokens de saída | 4,08 milhões |
| **custo total** | **US$ 901,96** |
| sessão principal | US$ 492,10 — **55%** |
| subagentes | US$ 409,86 — 45% |

### Por papel

| papel | invocações | custo | por invocação | turnos/invocação |
|---|---|---|---|---|
| `dev` | 232 | US$ 269,05 | US$ 1,16 | 28,0 |
| `scout` | 40 | US$ 3,18 | US$ 0,08 | 14,2 |
| `tester` | 25 | US$ 9,60 | US$ 0,38 | 24,4 |
| outros (visual-dev, general-purpose, Explore…) | 31 | US$ 128,03 | — | — |

`dev` em detalhe: mediana de **22** turnos, p90 **59**, máximo **169**.

### A alavanca: custo por faixa de turnos

| turnos | n | custo/invocação | custo/turno | % do custo de subagentes |
|---|---|---|---|---|
| 1-10 | 83 | US$ 0,08 | US$ 0,0139 | 1,6% |
| 11-30 | 140 | US$ 0,41 | US$ 0,0211 | 14,0% |
| 31-60 | 76 | US$ 1,86 | US$ 0,0435 | 34,5% |
| 61-120 | 27 | US$ 5,97 | US$ 0,0724 | 39,3% |
| 121+ | 2 | US$ 21,93 | US$ 0,1205 | 10,7% |

**O achado:** o mesmo turno custa **8,7× mais** numa invocação longa do que numa curta, porque
o contexto é reenviado inteiro a cada turno e só cresce. As **29 invocações** que passaram de
60 turnos são **8,8% do total** e **50% do custo de subagentes**.

Projeção do teto de turnos, re-loteando cada invocação longa no número mínimo de lotes de
31-60 turnos: **US$ 93,45** — 23% do custo de subagentes, **10% da conta total**.

## Quatro ressalvas, e elas importam

1. **Estes números descrevem o comportamento _anterior_** às mudanças do plugin. Nada foi
   medido depois.
2. **Uma pessoa, 43 sessões, 30 dias.** Não é amostra de equipe.
3. **A projeção depende de premissa.** Ela assume que a tarefa cortada no teto cabe no número
   mínimo de lotes. Se cada tarefa longa virar três lotes em vez de dois, a economia cai para
   perto de 1%. O ganho real está em **cortar a invocação que foge de controle**, não em
   espremer as normais.
4. **Uma medição anterior deste mesmo período estava errada** e chegou a circular: ela contava
   turnos sem deduplicar por `message.id`, e o Claude Code grava a mesma mensagem várias vezes
   no `.jsonl` — 8.883 de 11.859 mensagens aparecem repetidas, algumas 10 vezes. O fator era
   exatamente **2,00×**. A distribuição por faixa saía deslocada para cima, sugerindo 27
   invocações acima de 121 turnos quando são **2**. Se você vir por aí "23.648 turnos" ou
   "8% das invocações = 33% da conta", são os números velhos.

## Como refazer a medição

```
cd <repositório onde o Forge foi usado>
forge-tokens --desde AAAA-MM-DD
```

O que comparar, em ordem de importância:

1. **A distribuição por faixa de turnos.** É onde o teto aparece primeiro. Se ele estiver
   funcionando, as faixas 61-120 e 121+ encolhem e a 31-60 engorda — mesmo trabalho, contexto
   começando limpo mais vezes.
2. **`invocações acima do teto do próprio papel`** — eram 22 de 328 (7%). O hook devolve
   `PARCIAL` nesse ponto; a linha deve cair para perto de zero.
3. **Custo por turno na faixa alta.** É a métrica menos sujeita a variação de volume de
   trabalho.
4. **A proporção sessão × subagentes.** A sessão principal custou mais que todos os
   subagentes somados (55% × 45%) — é o que o `scout` existe para atacar, tirando varredura do
   contexto que é reenviado a cada turno.
