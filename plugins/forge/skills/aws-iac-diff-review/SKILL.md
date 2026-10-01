---
name: aws-iac-diff-review
description: Use depois que cdk diff ou terraform plan roda, antes de pedir aprovação ao usuário — checklist para ler o diff com critério em vez de só exibi-lo.
---

# Revisão Crítica de Diff de Infraestrutura

O diff ser exibido não significa que foi lido com critério. Antes de pedir
aprovação, passe pelo checklist abaixo linha a linha — não apenas cole o diff
cru e peça "pode seguir?".

## O que procurar

**IAM ampliado**
- Policy ficou mais permissiva (novo `Action` com wildcard, `"*"` em
  `Resource` onde antes era específico).
- Novo principal confiável (`Principal` novo num trust policy, `AssumeRole`
  liberado para conta ou serviço que não tinha acesso antes).

**Recurso stateful sem proteção**
- Bucket S3, tabela (DynamoDB/Iceberg), banco (RDS) sendo criado ou alterado
  sem `RemovalPolicy`/`DeletionPolicy` de retenção equivalente.
- Um `replace` nesse tipo de recurso é dado perdido, não indisponibilidade
  temporária — trate como o achado mais grave do diff.

**Exposição pública nova**
- Security group com regra de entrada aberta (`0.0.0.0/0`) onde antes não
  havia.
- Bucket ou recurso ficando público, ou perdendo bloqueio de acesso público.
- Endpoint novo sem autenticação (API Gateway/Lambda URL sem auth, Cognito
  removido de um recurso que tinha).

**Replace vs. update**
- O diff do CDK/Terraform indica explicitamente quando é `replacement`
  (CDK marca com `[-]`/`[+]` no mesmo recurso, Terraform mostra
  `# forces replacement`). Em recurso sem estado (Lambda, IAM role sem dado
  anexado) isso é rotina. Em recurso com estado, replacement é perda de dado
  mesmo que o nome do recurso pareça igual.

## Ao apresentar ao usuário

Feche resumindo em linguagem simples **o que muda de fato** — não cole o
diff bruto como resposta. Se algum item da lista acima apareceu, abra com
ele antes do resto ("este diff recria a tabela X, os dados atuais se
perdem"), mesmo que o diff completo tenha dezenas de linhas neutras.
