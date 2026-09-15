---
name: search-before-code
description: Use ao encontrar um erro de execução ou ao usar uma tecnologia/lib pela primeira vez no projeto — pesquisar na internet (com o ano 2026) antes de agir.
---

# Search Before Code

## Regra OBRIGATÓRIA — Pesquisar antes de agir

### Gatilho 1: Erro de execução

**SEMPRE que um comando ou código executado retornar erro**, pesquisar na internet ANTES de tentar corrigir.

```
❌ Não faça: tentar corrigir no escuro com base em suposições
✅ Faça: pesquisar o erro exato + 2026 e aplicar a solução encontrada
```

#### Como pesquisar um erro:
- Use a mensagem de erro exata (ou a parte mais específica dela)
- Sempre inclua o ano **2026** na busca para garantir soluções atuais
- Inclua o contexto tecnológico relevante

**Exemplos de queries:**
```
"Cannot find module 'better-sqlite3' tsx 2026"
"pnpm install EACCES permission denied 2026"
"playwright chromium not found linux 2026"
"aws lambda timeout error python 2026"
"tsc error TS2307 cannot find module 2026"
```

---

### Gatilho 2: Tecnologia/lib sendo usada pela primeira vez no projeto

**SEMPRE que for usar uma tecnologia, biblioteca ou serviço que ainda não foi usado no projeto**, pesquisar como fazer ANTES de escrever o código.

```
❌ Não faça: escrever código baseado em conhecimento desatualizado
✅ Faça: pesquisar "como usar [tecnologia] em [contexto] 2026" antes de implementar
```

#### Como identificar esse gatilho:
- Vai usar uma lib que não está no package.json/requirements.txt do projeto
- Vai integrar com um serviço externo (AWS, Stripe, Twilio, etc.)
- Vai usar um recurso avançado de uma lib (ex: DuckDB com Iceberg, Lambda com container)
- Vai configurar algo de infraestrutura (Docker, CDK, Terraform)

**Exemplos de queries:**
```
"como usar DuckDB com AWS Lambda 2026"
"DuckDB Iceberg S3 Python Lambda 2026"
"better-sqlite3 Express TypeScript setup 2026"
"Playwright headless Linux CI 2026"
"AWS CDK Python Lambda container image 2026"
"React Query v5 setup Vite 2026"
```

---

## Fluxo obrigatório

### Para erros:
```
Executou comando/código
  ↓ deu erro
Pesquisar: "[erro exato] 2026"
  ↓
Ler a solução
  ↓
Aplicar a correção baseada na pesquisa
  ↓
Executar novamente
```

### Para tecnologia nova:
```
Vai usar [tecnologia] pela primeira vez
  ↓
Pesquisar: "como usar [tecnologia] em [contexto] 2026"
  ↓
Ler a documentação/exemplos atuais
  ↓
Implementar baseado no que foi encontrado
```

---

## ⛔ Anti-patterns proibidos

- ❌ Tentar corrigir um erro sem pesquisar (adivinhar a solução)
- ❌ Usar sintaxe/API de memória sem verificar se ainda é válida em 2026
- ❌ Repetir a mesma tentativa que já falhou sem buscar nova informação
- ❌ Pesquisar sem incluir o ano 2026 (risco de soluções desatualizadas)

---

## ✅ Quando NÃO é necessário pesquisar

- Erro de sintaxe óbvio (ex: faltou fechar um parêntese)
- Tecnologia já usada e funcionando no projeto (ex: já tem Express configurado)
- Correção simples de lógica que não envolve APIs externas
