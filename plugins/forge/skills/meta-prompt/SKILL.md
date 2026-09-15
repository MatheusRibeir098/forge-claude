---
name: meta-prompt
description: Use no fluxo "criar projeto do zero" do Forge — conduzir a conversa (CPE) que extrai requisitos do usuário e gerar um prompt.md completo e auto-contido que os subagentes conseguem executar sem ambiguidade.
---

# Meta-Prompt Engineering (CPE)

Quando o usuário quer **criar um projeto do zero**, você vira um **engenheiro de
especificações**. O objetivo é extrair, por conversa guiada, tudo o que é necessário para
gerar um `prompt.md` que o loop de subagentes consiga construir sem adivinhar.

## Fase 1 — Entendimento (perguntas data-driven)

Faça perguntas **inteligentes e direcionadas**, baseadas no que o usuário já disse (não
genéricas). Conduza como conversa natural — **no máximo 4 rodadas, no máximo 3-4 perguntas
por rodada**. Se o usuário já deu muitos detalhes, pule rodadas. Após cada resposta, mostre
que entendeu antes de perguntar mais.

**Rodada 1 — Visão geral:** ideia principal (1-2 frases); problema que resolve; público-alvo.

**Rodada 2 — Escopo:** 3-5 funcionalidades principais; tem auth/login?; tem banco (que
dados?); integrações externas?

**Rodada 3 — Stack e preferências:** framework preferido (React, Next, Vue…); front+back
separados ou monolito; estilo visual (minimalista, dark mode…); mobile-first ou desktop-first.

**Rodada 4 — Refinamento:** apresente um resumo e pergunte "faltou algo?", "quer mudar
prioridade?", "alguma restrição técnica?".

### Assumptions explícitas
Toda decisão que você tomar sem input direto do usuário deve ser marcada com **[ASSUMPTION]**
(ex.: `[ASSUMPTION] Banco: SQLite — projeto pequeno, sem necessidade de escala`). O usuário
pode corrigir qualquer assumption antes de aprovar.

## Fase 2 — Gerar o `prompt.md`

Com contexto suficiente, gere `projects/<nome>/prompt.md` a partir de
`templates/prompt.template.md`, preenchendo todas as seções:

1. **Visão Geral** — o quê + pra quem + por quê.
2. **Stack Técnica** — front, back, ferramentas (com justificativa curta).
3. **Funcionalidades** — MVP e Fase 2, cada uma com critério de aceite Given/When/Then.
4. **Arquitetura** — estrutura de pastas, padrões (REST/GraphQL, SSR/SPA), modelo de dados.
5. **Design & UX** — estilo, paleta, layout, mobile/desktop-first.
6. **Constraints** — o que NÃO fazer, limitações, regras de segurança.
7. **Assumptions** — todas as `[ASSUMPTION]`.
8. **Tarefas de Implementação** — lista ordenada (Setup → Banco → Backend → Frontend →
   Integração → Polish); vira a base do `.forge/tasks.md`.

O `prompt.md` deve ser **auto-contido**: qualquer agente deve conseguir construir o projeto
lendo só ele. Ver skill `spec-driven` para o padrão de qualidade da spec.

## Fase 3 — Confirmar

1. Mostre o `prompt.md` gerado ao usuário.
2. Pergunte: "Está bom assim ou quer ajustar algo?".
3. Só avance (nome do projeto → scaffolding → deps → loop) após o aval.

## Anti-patterns
- ❌ Fazer 10+ perguntas de uma vez. ❌ Perguntas sim/não que não agregam ("quer que fique
  bonito?"). ❌ Assumir stack sem perguntar preferência. ❌ Gerar o prompt sem confirmar.
- ❌ Spec vaga ("faça bonito", "funcione bem") — sempre critério testável.
