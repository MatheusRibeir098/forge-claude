---
type: regex
pattern: '(?=[\s\S]*\bevid[êe]ncia)(?=[\s\S]*\bhip[oó]tese)'
flags: i
target: last_message
min: 1
---

A skill `investigacao-incidente-aws` manda separar, no relatório final, o que é evidência
(logs/eventos com timestamp) do que é hipótese (explicação plausível, não provada). Exigir as
duas palavras na resposta final é um proxy de que o agente tratou isso como investigação
estruturada — timeline e causa correlacionada — em vez de só declarar "encontrei o bug" e
propor/aplicar uma correção como se fosse fato provado.
