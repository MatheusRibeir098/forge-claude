---
type: regex
pattern: '(?=[\s\S]*\b(conta|account)\b)(?=[\s\S]*\b(perfil|profile)\b)(?=[\s\S]*\b(regi[ãa]o|region)\b)'
flags: i
target: last_message
min: 1
---

A resposta final precisa informar ao usuário em qual conta, perfil e região o número de custo
foi apurado — não basta devolver o valor total calado sobre onde ele veio. As três menções
precisam aparecer na mesma resposta.
