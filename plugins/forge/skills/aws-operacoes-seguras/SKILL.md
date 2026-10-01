---
name: aws-operacoes-seguras
description: Use antes de rodar qualquer comando `aws` CLI, MCP AWS, ou qualquer ação que toque conta AWS real — confirma identidade, classifica o comando por risco e decide quem executa o quê.
---

# Operações Seguras em Conta AWS Real

## Confirme onde você está antes de agir

Antes do **primeiro comando** que toca uma conta, rode `aws sts
get-caller-identity --profile <profile>` — nunca omita `--profile`, nunca
suponha o perfil `default`. Mostre ao usuário **conta, perfil e região** antes
de prosseguir. Ver `credenciais-ambiente` para mapear qual profile é qual
account/role.

## Se faltar mapa, pergunte

Antes de escolher um profile, consulte a skill `credenciais-ambiente` se ela existir. Se ela
**não existir**, ou se o profile necessário **não estiver mapeado** nela, **pergunte ao
usuário** qual usar — nunca adivinhe nem caia no `default`. Ofereça registrar a resposta
rodando `/forge:setup`, para a próxima vez já vir mapeada.

Isso não substitui o `sts get-caller-identity` acima: o mapa diz o que **deveria** ser, o
`sts` diz o que **é**. Confirme os dois sempre, mesmo quando a skill existe.

## Três categorias de comando

1. **Leitura — livre.** `describe-*`, `list-*`, `get-*` (ex.: `aws rds
   describe-db-instances`, `aws s3api list-buckets`, `aws ec2
   describe-instances`). Não exige confirmação.
2. **Mutação — avise antes.** `create-*`, `update-*`, `put-*`, `attach-*` (ex.:
   `aws lambda update-function-code`, `aws rds modify-db-instance`, `aws iam
   attach-role-policy`). Diga ao usuário **o que vai mudar e em qual conta**
   antes de rodar — não depois.
3. **Destrutivo/irreversível — o agente não executa.** `delete-*`, `rm`,
   `terminate-*`, `schedule-key-deletion` (ex.: `aws s3 rm --recursive`, `aws
   rds delete-db-instance`, `aws ec2 terminate-instances`, `aws
   cloudformation delete-stack`). Descreva o comando e devolva a decisão ao
   usuário — nunca execute, mesmo com autorização que pareça implícita na
   conversa.

## Perfil de menor privilégio

Se existir um profile read-only que resolve a tarefa, use-o. Nunca escolha um
profile de administrador (ex.: `dati_labs`, AdministratorAccess) só porque "é
o que funciona". Ver `credenciais-ambiente` para os profiles disponíveis.

## Produção é diferente

Se o perfil ou a account indicar produção (ex.: `dati_analytics_prd`), diga
isso em voz alta ao usuário antes de agir — **mesmo em leitura**. Silêncio
sobre "isto é produção" é o primeiro erro, não o comando em si.

## Subagentes

- `tester` em modo `contrato`: roda **somente leitura** em conta AWS real.
  Qualquer mutação ou comando destrutivo está fora do seu mandato, mesmo que
  pareça necessário para validar a tarefa.
- `dev`: não toca conta real para "testar". Validação de infraestrutura usa
  `cdk diff`/`terraform plan` (leitura) ou mocks — nunca `deploy`/`apply`
  real só para checar se o código funciona.
