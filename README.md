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

### 🔒 Papel é imposto por hook, não pedido no prompt

Três regras que o modelo não pode esquecer, porque não dependem dele:

| Regra | Como é imposta |
|---|---|
| O orquestrador **não escreve código de produto** | `PreToolUse` bloqueia por caminho; subagentes passam pela distinção de `agent_type` |
| O `dev` **não valida** — não sobe servidor, não roda E2E, não tira print, não bate na app por HTTP | `PreToolUse` nega esses comandos quando `agent_type` é `dev`. Ele mantém `tsc`/`build`/lint/teste unitário, que é o `build_ok` dele |
| Nenhum subagente passa de **~45 turnos** | contador por `agent_id`; no teto, retorna `PARCIAL` e o Forge re-loteia |

A segunda nasceu de uma medição desconfortável: o `tester` foi invocado **4 vezes contra 180
do `dev`**, e 78% dos `dev` estavam validando a si mesmos. Além de ser juiz em causa própria,
sai caro — `dev` que valida rodou 84 turnos de mediana contra 32 de quem não valida, e 20%
deles estouraram a faixa de 121+ turnos (US$ 14,64 por invocação). A iteração "sobe → testa →
falha → corrige" acontecia no contexto que é reenviado inteiro a cada turno; no `tester` ela
roda em contexto limpo e descartável.

Resultado: o contexto do orquestrador fica limpo para o que ele faz bem — decompor, revisar e
decidir; e o do `dev`, para escrever código.

### 📸 Nada passa sem prova

O `tester` não aprova por leitura de código. Ele sobe a aplicação em background, roda E2E com
Playwright, captura prints do que a tarefa mudou, **analisa as imagens** e devolve um veredito
estruturado. Reprovou? O erro volta para o `dev` como briefing de correção, com contagem de
tentativas.

As imagens ficam **dentro do contexto do tester**, que é descartado ao fim da invocação — o
orquestrador recebe a falha descrita em texto, nunca a imagem. A validação visual sai de graça
no turno seguinte, e o teto de 5 prints existe para manter o foco no que a tarefa mudou, não
para economizar: medindo os transcripts, imagem deu ~1% do consumo.

### 💰 Barato por medição, não por palpite

As 35 sessões deste repo foram medidas token a token (`~/.claude/projects/*/subagents/*.jsonl`):
2,65 bilhões de tokens processados, **55% deles nos subagentes**, e dentro dos subagentes
**55% do custo é contexto reenviado** (`cache_read`). O que a medição mostrou:

- **Turno é o que custa, não imagem.** O custo de uma invocação foi de **US$ 0,04** (até 10
  turnos) a **US$ 14,64** (121+ turnos) — 366×. O contexto do subagente cresce e é reenviado
  inteiro a cada turno, então o custo *por turno* também sobe (5,4× entre as duas faixas).
  Imagem, o suspeito óbvio, deu **~1%**.
- **Teto de turnos imposto por hook.** ~26 chamadas de ferramenta por `dev` (≈45 turnos). No
  limite ele devolve `status: PARCIAL` com `feito`/`falta`/`proximo_briefing`, e o
  orquestrador re-loteia — trabalho parcial bem descrito, não retrabalho. Esse único corte
  responde por ~76% da conta de subagentes.
- **Sonnet por padrão, opus sob demanda.** Medido, `dev` em opus custou 2,8× por invocação.
  O orquestrador promove só em arquitetura ou destravamento de Loop Travado.
- **Bash foi 61% do que os subagentes ingeriram.** Os briefings mandam usar `Grep`/`Glob`/
  `Read` (com `limit`) em vez de `grep`/`find`/`cat`, filtrar na fonte e nunca reler o que já
  está no contexto.
- **Skills sob demanda.** O orquestrador nomeia 1–2 skills por briefing; nada de carregar 11
  "por precaução". No boot, cada skill custa só a sua linha de descrição.
- **Arquivos de controle com teto.** `progress.md` mantém os ciclos recentes; o resto vai
  para o histórico, que não é lido no loop.

E o que a medição **descartou**: paralelismo não custa caro aqui. A tese de que o fan-out paga
`cache_write` a preço de cache frio não se sustentou nos dados — 3.448 tokens de `cache_write`
por turno em invocações solo contra 3.349 em lote. O Invariante 5 fica de pé.

### 🧭 Estado em disco, não na memória

Cada projeto carrega `.forge/tasks.md` (backlog e lotes), `.forge/progress.md` (ciclos
recentes), `.forge/progress-historico.md` (arquivo) e `.forge/screenshots/`. Fechou o notebook
no meio? Reabre e continua de onde parou — a fonte da verdade está em arquivo, não no
histórico da conversa.

## O time

| Papel | Quem é | Do que é dono |
|---|---|---|
| 🔥 **Forge** | a sessão principal | requisitos, spec, decomposição, briefings, revisão, relatório |
| 🛠️ **dev** | subagente (`sonnet`, opus sob demanda) | **todo** o código de produto |
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

Seis invariantes valem em qualquer momento da sessão, sempre no contexto (`CLAUDE.md`):

| # | Invariante |
|---|---|
| 1 | O orquestrador **não escreve código de produto** — delega ao `dev` (reforçado por hook) |
| 2 | **Nunca** `git push` nem deploy por iniciativa própria — só sob ordem explícita |
| 3 | Mensagens de commit em **português** |
| 4 | Confirma antes de matar processo; pesquisa antes de usar tecnologia nova |
| 5 | **Paralelize por padrão** — o usuário não precisa pedir para adiantar trabalho |
| 6 | **Cada token reenviado é pago de novo** — teto de turnos por subagente, sonnet por padrão, validação delegada ao `tester`, output filtrado na fonte |

## Skills incluídas

Carregadas sob demanda, não de uma vez:

**Orquestração** — `orchestrator`, `meta-prompt`, `spec-driven`, `scaffolding`, `lessons-learned`
**Qualidade** — `clean-code`, `testing-strategy`, `e2e-playwright`, `seguranca`, `search-before-code`
**Frontend** — `modern-design`, `ui-design`, `react-patterns`, `typescript`, `tailwind`, `responsive`, `dark-mode`, `animations`, `performance`, `content-ux`
**Operação** — `safe-operations`, `no-deploy-no-push`, `git-profiles`

## Estrutura

```
forge-claude/
├── CLAUDE.md                  # os 6 invariantes — sempre no contexto
├── bin/forge                  # entrypoint
├── bin/forge-tokens           # medidor de consumo (lê os transcripts)
├── .claude/
│   ├── settings.json          # permissões + hook de imposição de papel
│   ├── agents/{dev,tester}.md
│   ├── commands/{forge,forge-new,forge-fix}.md
│   ├── hooks/
│   │   ├── deny-orchestrator-code-edits.sh   # quem orquestra não codifica
│   │   └── subagent-turn-budget.sh           # teto de turnos por subagente
│   └── skills/                # 23 skills carregadas sob demanda
├── templates/                 # prompt.template.md, .npmrc
└── projects/<nome>/           # projetos gerados (não versionados aqui)
    ├── prompt.md              # a spec
    └── .forge/                # tasks.md · progress.md · progress-historico.md · screenshots/
```

## RTK — opcional, e de propósito

O hook de turnos encadeia o [RTK](https://github.com/rtk-ai/rtk) para compactar a saída de
alguns comandos. **O binário não é versionado**: em máquina nova o hook testa
`[ -x $RTK_BIN ]` e simplesmente não delega — nada quebra, você só não ganha a compactação.
Para habilitar:

```bash
# o install.sh divulgado (rtk-ai.app/install.sh) responde 404 — não use `curl | bash`
V=0.47.0
curl -sSLO https://github.com/rtk-ai/rtk/releases/download/v$V/rtk-x86_64-unknown-linux-musl.tar.gz
curl -sSLO https://github.com/rtk-ai/rtk/releases/download/v$V/checksums.txt
sha256sum --check --ignore-missing checksums.txt        # confira antes de instalar
tar -xzf rtk-x86_64-unknown-linux-musl.tar.gz
install -m 755 rtk ~/.local/bin/rtk                     # ou aponte FORGE_RTK_BIN
```

**A delegação é restrita a uma lista fechada** (`RTK_OK` no hook): `git status|diff|show|
branch`, `find`, `ls`, `tree`, e os verificadores — `playwright`, `pytest`, `vitest`, `jest`,
`tsc`, `ruff`, `eslint`, inclusive nas formas que o Forge usa de fato (`pnpm exec …`,
`npx …`, `uv run …`, `python3 -m …`). Só leitura e verificação, e cada variante `rtk ...` está
liberada na allowlist do `settings.json`.

O motivo da restrição é de segurança, não de gosto: a reescrita acontece **antes** da checagem
de permissão, então ela troca o comando que as regras de `permissions` vão avaliar. Com o rtk
reescrevendo livremente, `git push` virava `rtk git push` e **deixava de casar com a regra `ask`
`Bash(git push:*)`** — furando a imposição do Invariante 2 — e `cat`/`ls`/`find` saíam da
allowlist, o que geraria prompt de permissão em cada comando do loop.

Quanto isso rende, medido rodando o hook do rtk sobre **os 7.127 comandos Bash reais** dos
transcripts: ele *toca* 55,5% do volume, mas a economia é **5,4% do Bash ≈ 3,3% do que os
subagentes ingerem ≈ US$ 40**. A razão de a cobertura alta render pouco: o volume que ele toca
é dominado por `rtk read` (1,7 mi chars) e `rtk grep` (0,8 mi), que no nível padrão devolvem
saída **idêntica** — o nível que comprime de verdade (`aggressive`) troca corpos de função por
`// ... implementation`, inútil para quem vai editar o arquivo.

E os "60–99%" que ele anuncia em test runner são reais — só não têm onde incidir aqui. O `dev`
roda muito teste (234 chamadas de playwright, 229 de tsc, 85 de pytest), mas o output médio já
é de ~600 a 1.400 chars, porque o Invariante 6 **já manda filtrar na fonte** (`| tail -30`).
O RTK chega para colher um ganho que o próprio design do Forge já colheu. Ele continua na
lista porque é risco zero e porque, se o ciclo de teste crescer, o filtro já está no lugar.

## Medindo o próprio custo

O Forge traz a régua junto:

```bash
bin/forge-tokens                     # onde o token foi gasto, em todas as sessões
bin/forge-tokens --desde 2026-09-04  # só depois de uma data — para comparar antes/depois
bin/forge-tokens --json              # para script
```

Ele lê os transcripts (`~/.claude/projects/*/subagents/*.jsonl`) e reporta orquestrador vs
subagentes, custo por tipo de subagente e a curva de custo por faixa de turnos. Todo número
deste README saiu dele — e você pode refazer a conta a qualquer momento em vez de confiar na
promessa de quem vende a otimização.

## Ajustando o orçamento de turnos

O teto vem calibrado pelos dados deste repo (razão medida: 1,73 turno por chamada de
ferramenta). Para afrouxar ou apertar, sem editar o hook:

```bash
FORGE_TURN_WARN=18  FORGE_TURN_CAP=26   # dev (padrão) — ≈31 e ≈45 turnos
FORGE_TESTER_WARN=30 FORGE_TESTER_CAP=45 # tester (padrão) — ele sobe servidor e roda E2E
```

Tetos mais folgados, com a economia estimada sobre os mesmos dados: 40 turnos → ~76% da conta
de subagentes; 60 → ~58%; 80 → ~42%.

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
