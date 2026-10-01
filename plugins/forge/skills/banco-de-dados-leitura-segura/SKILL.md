---
name: banco-de-dados-leitura-segura
description: Use antes de consultar banco de dados ou data lake — perfil read-only, LIMIT em exploração, e cuidado com PII vazando para log ou relatório.
---

# Leitura Segura de Banco de Dados e Data Lake

## Perfil e permissões

Use perfil/role **read-only** quando existir (ver `credenciais-ambiente` para
mapear qual profile é qual). Antes de rodar qualquer `UPDATE`, `DELETE`, `DROP`
ou `ALTER`, exija pedido **explícito** do usuário — exploração e diagnóstico
nunca justificam escrita.

## Exploração sempre com LIMIT

Toda query exploratória (descobrir schema, ver amostra de dados, checar
distribuição) leva `LIMIT`. Isso protege terminal e contexto de output
gigante — mas não confunda com economia de custo: em bancos ou data lakes
cobrados por volume escaneado, `LIMIT` pode não
reduzir o custo da query.

## PII e dado sensível

- Nunca copie coluna sensível (CPF, e-mail, telefone, dado financeiro
  identificável) para o relatório ou resumo se a pergunta não exigir aquele
  dado específico. Prefira contagem, agregação ou amostra mascarada.
- Log de terminal e output de comando também são superfície de vazamento —
  um `SELECT *` numa tabela com PII expõe a coluna no scroll do terminal
  mesmo que o relatório final não a cite.
- Se precisar validar que uma coluna sensível existe ou tem o formato
  esperado, confirme por `COUNT`/`DESCRIBE`/nome de coluna, não por valor.

## MCP com tool restrita a SELECT x acesso direto

Quando o acesso passa por um **MCP com tool já restrita a SELECT**, a rede de
proteção contra escrita acidental já existe no servidor — o cuidado aqui é só
com volume de dado exposto.

Em **acesso direto** (`psql`, cliente de data lake manual,
clientes de banco via linha de comando) **essa rede não existe**: nada impede
um `DELETE` sem `WHERE` ou um `SELECT *` sem `LIMIT`. Nesses casos, a
disciplina de leitura segura é inteiramente manual — revise a query antes de
rodar, não depois.
