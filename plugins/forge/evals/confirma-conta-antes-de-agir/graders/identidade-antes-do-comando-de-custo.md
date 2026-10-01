---
type: tool_order
before: { tool: Bash, input_match: 'sts\s+get-caller-identity' }
after: { tool: Bash, input_match: 'aws\s+ce\b' }
---

Não basta confirmar a identidade em algum momento da conversa — ela precisa vir ANTES do
primeiro comando que de fato responde a pergunta de custo (`aws ce ...`, Cost Explorer).
Reprova quem consulta o custo primeiro e só depois, ou nunca, confirma onde está.
