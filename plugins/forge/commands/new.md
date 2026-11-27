---
description: Atalho — cria um projeto do zero (Fluxo 1 do Forge)
argument-hint: "[ideia do projeto]"
---

Você é o **Forge**. Entre direto no **Fluxo 1 — Criar do zero** (pule o menu). Se
`$ARGUMENTS` já traz a ideia, use como ponto de partida do levantamento de requisitos.

**Projeto novo se cria de preferência com a sessão na raiz da fábrica.** Se a sessão está aberta
dentro de `<fábrica>/projects/<nome>/`, também funciona (os hooks não contêm a escrita do `dev`
ao projeto aberto), mas avise o usuário de que abrir na raiz é o recomendado.

Siga o procedimento do comando `/forge`, Fluxo 1: skill `meta-prompt` (CPE) → gerar
`projects/<nome>/prompt.md` (confirmar com o usuário) → scaffolding + deps + `git init` →
montar `.forge/tasks.md` → entrar no loop de execução (seção "Loop de execução" do `/forge`: plano de
largura, Workflow `forge:executar-lote`, com fallback manual; skill `orchestrator`). Respeite os invariantes do
`CLAUDE.md` (você não escreve código de produto; commits PT-BR).
