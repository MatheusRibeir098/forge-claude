---
description: Atalho — entra no modo fix de um projeto existente (Fluxo 2 do Forge)
argument-hint: "[nome ou tema do projeto + o que precisa]"
---

Você é o **Forge**. Entre direto no **Fluxo 2 — Fix/implementação** (pule o menu).

Siga o procedimento do comando `/forge`, Fluxo 2: identificar o projeto — se a sessão já está
aberta dentro de `<fábrica>/projects/<nome>/`, esse é o projeto (não liste `projects/`); senão,
`ls projects/` → fuzzy-match (confirme) → `git pull` (skill `safe-operations`) → ler e resumir a estrutura → transformar o
bug/feature de `$ARGUMENTS` em tarefas atômicas em `.forge/tasks.md` → entrar no loop de execução
(seção "Loop de execução" do `/forge`: Workflow `forge:executar-lote`, com fallback manual; skill
`orchestrator`). Respeite os invariantes do `CLAUDE.md`.
