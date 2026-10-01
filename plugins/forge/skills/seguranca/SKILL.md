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

2. **A ação modifica infraestrutura real (banco de dados, DNS, cloud, permissões)?**
   - Se sim → confirme com o usuário antes de executar.

3. **A ação é irreversível?**
   - Deleção de recursos, drop de tabelas, remoção de buckets ou volumes → SEMPRE confirmar.

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
