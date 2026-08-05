<div align="center">

# 🔥 Forge (Claude Code)

**Fábrica de projetos com um orquestrador e subagentes headless — sem tmux.**

</div>

---

## O que é

O Forge cria e mantém projetos de software conversando com você. Você fala **só com o Forge**:
ele levanta os requisitos, monta a spec, decompõe em tarefas e coordena dois subagentes
(`dev` e `tester`) até entregar — reportando o progresso em linguagem natural.

Esta é a versão **Claude Code** do Forge. Substitui a versão anterior (kiro-cli + tmux), cuja
coordenação entre agentes dependia de `tmux send-keys`/`sleep`/scraping de terminal — a fonte
dos travamentos. Aqui a comunicação é **retorno estruturado de subagente**, determinística.

O progresso dos subagentes `dev`/`tester` aparece em **`/tasks`** e nas notificações da
sessão. (Em execuções headless, `claude -p --output-format stream-json --forward-subagent-text`
espelha o texto dos subagentes; na sessão interativa isso não é necessário.)

```
Você
  ↓ linguagem natural
Forge (orquestrador = sessão principal)
  ├─ subagente dev     → escreve o código        (retorno estruturado)
  └─ subagente tester  → valida + E2E + prints    (retorno estruturado)
```

## Pré-requisitos

- Claude Code (`claude`) 2.1+ autenticado
- `pnpm`, `node`
- Para os testes visuais: Playwright/Chromium (`npx playwright install chromium`)

## Como usar

```bash
# opção A — via script (não altera seu shell)
~/forge-claude/bin/forge

# opção B — função de conveniência (adicione ao ~/.zshrc)
forge() { cd ~/forge-claude && claude --forward-subagent-text "$@"; }
```

Dentro da sessão, digite **`/forge`** e escolha:

```
1. 🆕 Criar um projeto do zero
2. 🔧 Fix/implementação em projeto existente
```

Atalhos: `/forge-new <ideia>` e `/forge-fix <projeto + pedido>`.

## Como funciona (arquitetura)

| Papel | Quem | Mecanismo |
|---|---|---|
| **Forge** (hub + orquestrador) | a sessão principal | comando `/forge` + `CLAUDE.md` + skill `orchestrator` |
| **dev** | subagente `.claude/agents/dev.md` | Task tool; escreve todo o código |
| **tester** | subagente `.claude/agents/tester.md` | Task tool; build + E2E Playwright + screenshots |

- O orquestrador **não escreve código de produto** — um hook `PreToolUse` (deny-por-caminho)
  bloqueia a sessão-raiz e libera os subagentes (distinção por `agent_type` no payload).
- Servidores de longa duração rodam via `Bash(run_in_background)` — sem sessão tmux, sem
  foreground travando.
- Estado do loop por projeto: `projects/<nome>/.forge/{tasks.md, progress.md, screenshots/}`.

## Estrutura

```
forge-claude/
├── CLAUDE.md                 # invariantes sempre-presentes
├── bin/forge                 # entrypoint
├── .claude/
│   ├── settings.json         # permissões + hook de imposição de papel
│   ├── agents/{dev,tester}.md
│   ├── commands/{forge,forge-new,forge-fix}.md
│   ├── hooks/deny-orchestrator-code-edits.sh
│   └── skills/               # orchestrator, meta-prompt, spec-driven, frontend-*, ...
├── templates/                # prompt.template.md, .npmrc
└── projects/<nome>/          # projetos gerados
```

## Roadmap

Fora do núcleo atual: agentes especializados (quicksight, pentest-web, frontend-designer),
pipeline de EPICs (planner/decomposer/coder) com paralelismo real via `claude --bg` +
`claude agents` e worktrees por EPIC.
