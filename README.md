<div align="center">

# 🔥 Forge

### Uma fábrica de software que cabe numa conversa.

**Você descreve. O Forge decompõe, delega para um time de subagentes e entrega validado.**

[![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1%2B-D97757?style=flat-square)](https://claude.com/claude-code)
[![Subagentes](https://img.shields.io/badge/subagentes-dev%20%2B%20tester-6366f1?style=flat-square)](#o-time)
[![Paralelismo](https://img.shields.io/badge/paralelismo-por%20padrão-16a34a?style=flat-square)](#-paralelismo-é-o-padrão)
[![Sem tmux](https://img.shields.io/badge/tmux-não%20precisa-64748b?style=flat-square)](#por-que-não-tem-tmux)

</div>

---

## O que é

O Forge transforma o Claude Code num **orquestrador de projetos**. Você conversa com **um
único agente** — ele levanta os requisitos, escreve a spec, quebra em tarefas atômicas e
coordena dois subagentes especializados até o software existir, funcionando e testado.

Você nunca abre um terminal de agente. Nunca fala com o `dev`. Nunca fica olhando um
processo para saber se acabou. Você conversa, ele reporta.

```
você ──▶ 🔥 Forge ──┬──▶ 🛠️  dev      escreve todo o código
                    └──▶ 🔍 tester   sobe, testa, printa, aprova ou reprova
```

## A ideia em 30 segundos

```
você  › /forge
      › quero um app pra controlar minhas assinaturas mensais

🔥    › Três perguntas antes de eu montar a spec:
        1. Só você usa ou tem login? 2. Precisa de alerta de renovação?
        3. Web, ou também no celular?

você  › só eu, sim, e responsivo

🔥    › Spec pronta em projects/assinaturas/prompt.md — 11 tarefas em 4 lotes.
        Começando o lote 1: 3 devs em paralelo (schema, API, layout base)
        + 1 agente pesquisando a lib de notificação.

        ✅ T1 schema  ✅ T2 API  ✅ T3 layout    tester: PASSOU (4 prints)
        Lote 2 rodando. Faltam 6 tarefas.
```

## Por que ele é diferente

### 🧠 Um só interlocutor

O modelo mental é de **delegação**, não de ferramenta. Você não escolhe qual agente chamar
nem monta prompt para subagente: o Forge traduz o que você quer em briefings auto-contidos.
Se algo travar, ele volta e **pergunta** — em português, sem jargão de execução.

### ⚡ Paralelismo é o padrão

Antes de **cada** invocação, o orquestrador roda um checkpoint de quatro perguntas: tem
tarefa irmã liberada? tem pesquisa para adiantar? tem validação pendente? vale uma segunda
opinião? Tudo que der "sim" é disparado **na mesma leva**.

O backlog já nasce agrupado em lotes, com as listas de arquivos cruzadas para garantir que
dois agentes nunca escrevam no mesmo lugar. Você não precisa pedir para ele acelerar.

### 🔒 Quem orquestra não codifica

Um hook `PreToolUse` bloqueia, por caminho, qualquer tentativa do orquestrador de escrever
código de produto — e libera os subagentes pela distinção de `agent_type`. Não é uma regra
no prompt que o modelo pode esquecer: é imposição da ferramenta.

Resultado: o contexto do orquestrador fica limpo para o que ele faz bem — decompor,
revisar e decidir.

### 📸 Nada passa sem prova

O `tester` não aprova por leitura de código. Ele sobe a aplicação em background, roda E2E
com Playwright, tira prints em desktop (1280×720) e mobile (375×667), **analisa as imagens**
e devolve um veredito estruturado. Reprovou? O erro volta para o `dev` como briefing de
correção, com contagem de tentativas.

### 🧭 Estado em disco, não na memória

Cada projeto carrega `.forge/tasks.md` (backlog e lotes), `.forge/progress.md` (log
append-only de cada ciclo) e `.forge/screenshots/`. Fechou o notebook no meio? Reabre e
continua de onde parou — a fonte da verdade está em arquivo, não no histórico da conversa.

## O time

| Papel | Quem é | Do que é dono |
|---|---|---|
| 🔥 **Forge** | a sessão principal | requisitos, spec, decomposição, briefings, revisão, relatório |
| 🛠️ **dev** | subagente (`opus`) | **todo** o código de produto |
| 🔍 **tester** | subagente (`sonnet`) | build, E2E, screenshots, veredito |

Cada subagente devolve **JSON estruturado** — o orquestrador decide olhando dados, nunca
adivinhando por texto de terminal.

## Instalação

```bash
git clone https://github.com/MatheusRibeir098/forge-claude.git ~/forge-claude
cd ~/forge-claude && npx playwright install chromium
```

Pré-requisitos: [Claude Code](https://claude.com/claude-code) 2.1+ autenticado, `node` e `pnpm`.

## Uso

```bash
~/forge-claude/bin/forge
```

Ou, para virar um comando de qualquer lugar (no `~/.zshrc`):

```bash
forge() { cd ~/forge-claude && claude --forward-subagent-text "$@"; }
```

Dentro da sessão:

| Comando | O que faz |
|---|---|
| `/forge` | Hub — pergunta se é projeto novo ou fix |
| `/forge-new <ideia>` | Vai direto para criação do zero |
| `/forge-fix <projeto + pedido>` | Bug ou feature em projeto existente |

Acompanhe os subagentes em **`/tasks`**.

## Por que não tem tmux

Coordenar agentes por `tmux send-keys` + `sleep` + scraping de terminal é frágil: você
infere que uma etapa acabou olhando texto na tela, e qualquer prompt inesperado trava o
loop. Aqui o fim de uma etapa é o **retorno da chamada do subagente** — determinístico.
Servidores de longa duração sobem via `Bash(run_in_background)`, sem nada segurando o
foreground.

## As regras da casa

Cinco invariantes valem em qualquer momento da sessão, sempre no contexto (`CLAUDE.md`):

| # | Invariante |
|---|---|
| 1 | O orquestrador **não escreve código de produto** — delega ao `dev` (reforçado por hook) |
| 2 | **Nunca** `git push` nem deploy por iniciativa própria — só sob ordem explícita |
| 3 | Mensagens de commit em **português** |
| 4 | Confirma antes de matar processo; pesquisa antes de usar tecnologia nova |
| 5 | **Paralelize por padrão** — o usuário não precisa pedir para adiantar trabalho |

## Skills incluídas

Carregadas sob demanda, não de uma vez:

**Orquestração** — `orchestrator`, `meta-prompt`, `spec-driven`, `scaffolding`, `lessons-learned`
**Qualidade** — `clean-code`, `testing-strategy`, `e2e-playwright`, `seguranca`, `search-before-code`
**Frontend** — `modern-design`, `ui-design`, `react-patterns`, `typescript`, `tailwind`, `responsive`, `dark-mode`, `animations`, `performance`, `content-ux`
**Operação** — `safe-operations`, `no-deploy-no-push`, `git-profiles`

## Estrutura

```
forge-claude/
├── CLAUDE.md                  # os 5 invariantes — sempre no contexto
├── bin/forge                  # entrypoint
├── .claude/
│   ├── settings.json          # permissões + hook de imposição de papel
│   ├── agents/{dev,tester}.md
│   ├── commands/{forge,forge-new,forge-fix}.md
│   ├── hooks/deny-orchestrator-code-edits.sh
│   └── skills/                # 23 skills carregadas sob demanda
├── templates/                 # prompt.template.md, .npmrc
└── projects/<nome>/           # projetos gerados (não versionados aqui)
    ├── prompt.md              # a spec
    └── .forge/                # tasks.md · progress.md · screenshots/
```

## Roadmap

- Agentes especializados: `quicksight`, `pentest-web`, `frontend-designer`
- Pipeline de EPICs (planner → decomposer → coder) com worktree por EPIC
- Paralelismo real entre EPICs via `claude --bg` + `claude agents`

---

## Licença

[MIT](LICENSE) © Matheus Ribeiro

---

<div align="center">
<sub>Construído com <a href="https://claude.com/claude-code">Claude Code</a>.</sub>
</div>
