---
name: spec-driven
description: Use ao interpretar prompts como especificação de software — critérios de sucesso, contrato de output, tarefas auto-contidas e aceitação Given/When/Then.
---

# Spec-Driven Development

## Princípio
Tratar o prompt como uma especificação de software, não como texto livre. Specs bem escritas eliminam ambiguidade e reduzem retrabalho.

## Checklist de Qualidade do Prompt/Spec

1. **Critérios de sucesso** — o que define "pronto"?
2. **Contrato de output** — formato, estrutura, padrões esperados
3. **Constraints** — escopo, exclusões, o que fazer quando incerto
4. **Inputs** — contexto mínimo necessário
5. **Verificação** — como validar que está correto

## Formato de Critérios de Aceitação

Usar Given/When/Then para cada funcionalidade:
```
Given [contexto/pré-condição]
When [ação do usuário]
Then [resultado esperado]
```

Exemplo:
```
Given um usuário não autenticado
When ele acessa /dashboard
Then é redirecionado para /login
```

## Tarefas Auto-Contidas

Cada tarefa no prompt deve:
- Ser completável em uma sessão de agente
- Ter critérios de aceitação próprios
- Listar arquivos que serão criados/modificados
- Não depender de tarefas futuras (apenas de anteriores)

## Anti-patterns de Specs
- ❌ "Faça bonito" — vago, não testável
- ❌ "Funcione bem" — sem critério de sucesso
- ❌ Misturar decisão com implementação ("use useState para...")
- ❌ Spec maior que o código que ela descreve
