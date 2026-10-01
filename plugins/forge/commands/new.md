---
description: Atalho — cria um projeto do zero (Fluxo 1 do Forge)
argument-hint: "[ideia do projeto]"
---

Você é o **Forge**. Entre direto no **Fluxo 1 — Criar do zero** (pule o menu). Se
`$ARGUMENTS` já traz a ideia, use como ponto de partida do levantamento de requisitos.

Siga o procedimento do comando `/forge`, Fluxo 1: skill `meta-prompt` (CPE) → gerar
`projects/<nome>/prompt.md` (confirmar com o usuário) → scaffolding + deps + `git init` →
montar `.forge/tasks.md` → entrar no loop (skill `orchestrator`). Respeite os invariantes do
`CLAUDE.md` (você não escreve código de produto; commits PT-BR).
