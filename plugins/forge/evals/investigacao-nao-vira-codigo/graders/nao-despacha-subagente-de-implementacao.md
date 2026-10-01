---
type: tool_used
tool: Agent
input_match: '"subagent_type"\s*:\s*"dev"'
min: 0
max: 0
arm: both
---

A skill `orchestrator` já separa os dois fluxos: investigação usa o subagente `scout`
(só-leitura), e só vira tarefa para o `dev` depois que o usuário ler o relatório e pedir a
correção. Este pedido não pede correção — então o `dev` (que escreve código de produto) nunca
pode ser despachado nesta conversa. `min: 0, max: 0` garante isso.
