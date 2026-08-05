---
name: testing-strategy
description: Use ao decidir o escopo de testes de uma mudança — teste o que mudou, não o projeto inteiro. Escopo por tipo de mudança, ordem de execução e anti-patterns.
---

# Estratégia de Testes Inteligente

## Princípio: Teste o que mudou, não o projeto inteiro

### Escopo de testes por tipo de mudança

**Frontend-only (componentes, páginas, estilos):**
- Compilação: `cd frontend && npx tsc --noEmit`
- E2E focado: testar APENAS as páginas/fluxos afetados pela mudança
- Verificar: renderização, interações, navegação, responsividade
- NÃO rodar testes de backend se backend não foi alterado

**Backend-only (rotas, services, database):**
- Compilação: `cd backend && npx tsc --noEmit`
- Testes de API: curl/httpie nas rotas modificadas (200, 400, 404, 500)
- Verificar: response shape, status codes, edge cases
- NÃO rodar E2E de frontend se frontend não foi alterado

**Full-stack (ambos alterados):**
- Compilação de ambos
- Testes de API nas rotas afetadas
- E2E nos fluxos que usam as rotas alteradas

### Como determinar o escopo

1. Identifique quais arquivos foram modificados
2. Mapeie: arquivo → funcionalidade → fluxo do usuário
3. Teste APENAS os fluxos impactados
4. Se um componente é usado em 3 páginas mas só 1 foi afetada, teste só essa 1

### Ordem de execução

1. **Integridade** — compilação, tipos, imports (rápido, pega erros óbvios)
2. **Unitário/API** — funções e rotas específicas modificadas
3. **E2E** — fluxo completo do usuário que exercita a mudança

### Anti-patterns

- ❌ Rodar TODOS os testes E2E pra uma mudança de CSS
- ❌ Testar rotas de backend quando só mudou frontend
- ❌ Fazer grep/contagem de imports como "teste"
- ❌ Verificar arquivos que não foram tocados
- ❌ Declarar API OK sem testar CORS preflight OPTIONS
- ❌ Declarar Lambda OK sem verificar estrutura do ZIP
- ❌ Declarar testes passando usando NODE_ENV=test (bypassa auth real)
- ❌ Declarar E2E OK sem chegar na funcionalidade principal
- ❌ Testar fluxo com banco/dados vazio

---

## Pirâmide de testes para projetos com deploy AWS

```
        E2E contra produção (Playwright)
       ─────────────────────────────────
      Integração real (token Cognito + AWS)
     ─────────────────────────────────────
    API local (Supertest, NODE_ENV=test)
   ───────────────────────────────────────
  Unit (Jest, lógica isolada)
```

Cada camada testa o que a camada abaixo não cobre. Após deploy, sempre rodar integração real + E2E produção.
