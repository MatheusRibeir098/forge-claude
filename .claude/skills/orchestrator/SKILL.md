---
name: orchestrator
description: Use durante o loop de execução do Forge — como decompor um projeto/bug em tarefas, montar briefings, invocar os subagentes dev e tester, avaliar seus retornos estruturados e persistir progresso. Substitui todo o mecanismo antigo de tmux.
---

# Orquestração por subagentes (sem tmux)

Esta skill descreve como o **Forge** (a sessão principal, que é o antigo "monitor")
coordena os subagentes `dev` e `tester`. A comunicação é por **invocação de subagente com
retorno estruturado** — não há tmux, send-keys, capture-pane, sleep ou scraping de terminal.

## Modelo mental

```
Você (Forge / orquestrador)
  ├─ lê prompt.md + .forge/tasks.md → escolhe a próxima tarefa
  ├─ monta briefing auto-contido
  ├─ invoca subagente `dev`     → recebe retorno estruturado (JSON)
  ├─ revisa o retorno
  ├─ invoca subagente `tester`  → recebe veredito estruturado (JSON)
  └─ avalia → marca done / re-briefa → registra em .forge/progress.md
```

O "fim" de cada etapa é o **retorno da Task tool**, determinístico. Você nunca infere
conclusão observando um terminal.

## Arquivos de controle (fonte de verdade)

Ficam em `projects/<nome>/.forge/`:

- **`tasks.md`** — backlog de tarefas atômicas, ordenadas por dependência. Formato:
  ```markdown
  # Tarefas — <projeto>
  - [ ] T1 — <título> — depende de: nenhuma
  - [ ] T2 — <título> — depende de: T1
  - [x] T0 — Setup — depende de: nenhuma
  ```
- **`progress.md`** — log de cada ciclo (append-only). Registra, por tarefa/tentativa: o
  retorno do `dev` (build_ok, arquivos), o veredito do `tester` (PASSOU/FALHOU + screenshots),
  e a **contagem de tentativas** (para a regra Loop Travado).
- **`screenshots/`** — onde o `tester` salva as prints; ele retorna os caminhos.

Você (Forge) **pode** escrever nesses arquivos de controle — eles não são código de produto.
Você **não pode** escrever código-fonte (isso é do `dev`).

## Decompor em tarefas atômicas

Ao entrar no loop (após o `prompt.md` existir, no fluxo criar; ou após entender o bug, no
fluxo fix):

1. Leia o `prompt.md` (criar) ou a descrição do bug/feature (fix).
2. Quebre em **tarefas atômicas**, cada uma:
   - completável numa única invocação do `dev`;
   - com critério de aceitação próprio (Given/When/Then — ver skill `spec-driven`);
   - listando os arquivos que serão criados/alterados;
   - dependendo só de tarefas anteriores.
3. Grave em `.forge/tasks.md`. Apresente o plano ao usuário antes de começar a executar.

Ordem típica para projeto novo: Setup → Banco/schema → Backend (rotas/services) → Frontend
(páginas/componentes) → Integração front↔back → Polish (responsivo, dark mode, animações).

## Briefing para o `dev` (qualidade importa)

Um bom briefing é **auto-contido** — o subagente não tem o histórico da sua conversa. Inclua:

- **Arquivo(s)**: quais criar/editar (caminhos).
- **Objetivo**: o que a tarefa entrega, em 1-2 frases.
- **Contrato**: assinatura de API, shape de dados, props, comportamento esperado.
- **Critério de aceite**: Given/When/Then.
- **Contexto/padrões**: siga o padrão das rotas/componentes já existentes (cite um exemplo).
- **Restrições**: o que NÃO fazer.

Invoque o subagente `dev` passando esse briefing. Ele retorna:
```json
{ "status": "OK|BLOQUEADO", "arquivos_alterados": [...], "build_ok": true,
  "comandos_para_subir": [...], "resumo": "...", "pendencias": [...] }
```

### Revisão do retorno do dev
- `status: BLOQUEADO` → leia `pendencias`. Se for decisão de produto, **pergunte ao usuário**.
- `build_ok: false` → re-briefe com foco no erro (e acione a skill `search-before-code`).
- Fora do escopo / código duvidoso → re-briefe apontando o desvio.

## Briefing para o `tester` (curto e focado)

O `tester` valida **apenas** o que a tarefa implementou (não a suite inteira). Passe:

- **Como subir** o app (use `comandos_para_subir` que o `dev` retornou).
- **O que validar**: rotas/páginas/estados específicos desta tarefa.
- **Screenshots**: quais telas/estados capturar (desktop 1280×720 e mobile 375×667).

Ele retorna:
```json
{ "veredito": "PASSOU|FALHOU", "falhas": [{ "tipo": "...", "tela": "...", "descricao": "..." }],
  "screenshots": ["/caminho/abs/..."], "logs_relevantes": [...], "recomendacao_para_dev": "..." }
```

## Avaliar e fechar o ciclo

- **PASSOU** → marque a tarefa `[x]` em `.forge/tasks.md`, registre o ciclo em
  `.forge/progress.md` (retorno do dev + veredito + caminhos das screenshots) e vá para a
  próxima tarefa.
- **FALHOU** → monte um briefing de correção a partir de `falhas` + `recomendacao_para_dev`
  e volte a invocar o `dev`. Incremente a contagem de tentativas da tarefa em `progress.md`.

## ⚠️ Regra do Loop Travado

Conte as tentativas por tarefa em `.forge/progress.md`.

- Mesmo erro na **3ª tentativa** → **reformule o briefing do zero**, por um ângulo diferente
  (outra abordagem técnica), e acione `search-before-code` (pesquisar o erro exato + ano atual).
- Persistindo após a reformulação → **pare e pergunte ao usuário**. Você é a sessão principal,
  então basta uma mensagem normal — não há "terminal preso" de onde escapar.

Nunca fique em loop infinito re-briefando a mesma coisa.

## Servidores de longa duração

Quando o `tester` precisar subir backend/frontend, ele usa `Bash` com `run_in_background: true`
e lê o output depois. Não existe mais a sessão tmux `servers`; não há foreground travando nada.

## Regras de ouro

- O usuário fala só com você. Nunca diga "abra o terminal" ou "fale com o dev".
- Você **não escreve código de produto** — sempre delega ao `dev`.
- Reporte ao usuário de forma resumida: o que foi feito, o que está em andamento, o que falta.
- Se o usuário mudar de ideia no meio, adapte o `tasks.md`.
