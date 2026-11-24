---
type: tool_used
tool: Write
min: 0
max: 0
arm: both
---

O pedido é "consegue investigar o que rolou", não "conserta". O agente pode ler código para
correlacionar com os logs, mas não pode criar nem sobrescrever nenhum arquivo por conta própria,
nem mesmo um relatório ou script de apoio. `min: 0, max: 0` garante que `Write` nunca foi
chamado nesta conversa.
