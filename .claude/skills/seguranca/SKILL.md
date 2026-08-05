---
name: seguranca
description: Regras de segurança obrigatórias. Aplicar antes de executar qualquer ação crítica — infraestrutura real, comandos destrutivos, escopo do projeto e secrets.
---

# Segurança — Regras Obrigatórias

## Antes de Qualquer Ação

Todo agente DEVE verificar antes de executar:

1. **A ação está dentro da minha pasta de trabalho?**
   - Se não → PARE. Não execute.
   - Cada agente trabalha APENAS na sua pasta designada.

2. **A ação modifica infraestrutura real (AWS, banco de dados, DNS, IAM)?**
   - Se sim → confirme com o usuário antes de executar.
   - Nunca execute `cdk deploy`, `terraform apply`, `aws` CLI destrutivo sem confirmação explícita.

3. **A ação é irreversível?**
   - Deleção de recursos, drop de tabelas, remoção de buckets S3 → SEMPRE confirmar.

---

## AWS — Regras Específicas

- **Nunca** hardcodar credenciais, access keys ou secrets em código
- **Nunca** usar `*` em IAM policies — sempre least privilege
- **Nunca** fazer `cdk deploy` ou `aws` CLI em produção sem confirmação explícita do usuário
- Secrets vão no Secrets Manager ou Parameter Store, nunca em variáveis de ambiente no código
- Recursos devem ter tag `Environment` (dev/staging/prod) — nunca criar recurso sem saber o ambiente alvo
- Antes de criar qualquer recurso AWS, verificar se já existe um equivalente para evitar duplicação

## Comandos AWS Destrutivos — Requer Confirmação

Qualquer comando que contenha:
- `delete`, `remove`, `destroy`, `terminate`, `drop`
- `cdk destroy`
- `aws s3 rm`, `aws dynamodb delete-table`, `aws rds delete`

→ PARE e informe o usuário antes de executar.

---

## Escopo do Projeto

- Não instale dependências globais sem avisar o usuário
- Não modifique arquivos de configuração fora da sua pasta (`.env`, `package.json` raiz, etc.)
- Não exponha portas ou endpoints sem que esteja no design aprovado
- Não faça chamadas a APIs externas não previstas no design

---

## Secrets e Dados Sensíveis

- Nunca logar ou printar valores de secrets, tokens ou senhas
- Nunca commitar arquivos `.env` com valores reais
- `.env.example` com placeholders é permitido
- Usar `.gitignore` para arquivos sensíveis
