---
type: tool_used
tool: Bash
input_match: 'aws\s+sts\s+get-caller-identity'
min: 1
---

O pedido não diz conta, perfil nem região. Antes de tocar a conta para responder "quanto
gastamos esse mês", o agente precisa confirmar onde está com `aws sts get-caller-identity`
(ou equivalente) — não pode sair direto rodando o comando de custo no profile que calhar de
estar ativo.
