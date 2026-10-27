---
name: e2e-chrome
description: Use para validar UI de ponta a ponta no Chrome real do usuário via claude-in-chrome — subir o app, abrir aba da sessão, navegar, localizar elemento, preencher formulário, ler console e capturar evidência visual. Carregue quando a tarefa tem interface e o `tester` está em modo `browser`. Não use em tarefa sem navegador (MCP server, CLI, YAML, infra).
---

# E2E no Chrome do usuário

Não existe navegador headless aqui. Você dirige o **Chrome do usuário** (`google-chrome-stable`)
pela extensão do Claude. É um recurso compartilhado e vivo — as regras abaixo não são estilo.

## Passo a passo

### 1. Carregue as ferramentas — uma única chamada

Elas chegam **diferidas**: sem `ToolSearch` antes, a chamada falha. Uma query com a lista
inteira, nunca uma por ferramenta:

```
ToolSearch: select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__tabs_close_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__find,mcp__claude-in-chrome__form_input,mcp__claude-in-chrome__read_console_messages,mcp__claude-in-chrome__resize_window
```

### 2. Suba o app e espere ele responder

Antes de subir, **cheque se a porta está livre**. Porta ocupada por processo que não é seu
(o servidor de dev do usuário, por exemplo) **não se mata**: suba o seu em outra porta
(`--port 5174`, `PORT=3002`) ou pergunte ao Forge.

```bash
lsof -ti:5173 -sTCP:LISTEN && echo "5173 OCUPADA — use outra porta"
```

Servidores longos vão em **background** (`Bash` com `run_in_background: true`) — nunca
foreground, `&` ou `nohup`. **Guarde o PID do servidor que você subiu**: com `exec`, o
processo do servidor assume o PID que o `bash` gravou, e é só esse PID que você encerra no
fim.

```bash
mkdir -p .forge && bash -c 'echo $$ > .forge/tester-frontend.pid; exec pnpm dev --port 5173'
```

Confirme antes de abrir o navegador:

```bash
curl -sf http://localhost:5173 >/dev/null && echo "frontend OK"
curl -sf http://localhost:3001/api/health >/dev/null && echo "backend OK"
```

App que não sobe já é o veredito (`FALHOU`, `tipo: "build"`) — não abra aba.

### 3. Abra uma aba da sessão

`tabs_context_mcp` para ver o contexto, depois `tabs_create_mcp` para criar a aba. Numa
sessão nova, `tabs_context_mcp` devolve
`"No tab group exists for this session. Use createIfEmpty: true to create one."` — **resposta
normal**, não erro.

### 4. Navegue e exercite o fluxo

- `navigate` para a rota que a tarefa mudou (não pare na home se a funcionalidade está
  adiante).
- `find` para localizar elemento por descrição; `read_page` quando precisar da estrutura e
  `get_page_text` quando bastar o texto.
- `form_input` para preencher campos; `computer` para clicar, rolar e capturar.
- `resize_window` para trocar de viewport: desktop **1280x720** sempre, mobile **375x667**
  só quando **esta** tarefa mexeu no layout.

### 5. Leia o console com filtro

```
read_console_messages  →  pattern: "error|Uncaught|Warning: "
```

Console inteiro é despejo. Filtre por `pattern` e leve só o trecho para o JSON.

### 6. Capture evidência — teto de 5

Só os estados que **esta** tarefa mudou. Salve em `evidencias/`, dentro da pasta `.forge/` do projeto, com
nome descritivo (`checkout-erro-mobile.png`). Print é barato perto de um turno extra — então
capture o que prova, sem passeio. Quem vê a imagem é você: o Forge lê apenas a sua descrição
em texto.

### 7. Feche a aba e derrube os servidores

`tabs_close_mcp` na aba que **você** criou. Depois encerre **só os servidores que você
subiu**, pelo PID gravado no passo 2 (filhos primeiro, depois o processo):

```bash
for f in .forge/tester-*.pid; do
  pid=$(cat "$f"); pkill -P "$pid" 2>/dev/null; kill "$pid" 2>/dev/null; rm -f "$f"
done
```

**Nunca** mate por porta (`kill $(lsof -t -i:PORTA)`): a porta pode pertencer a um processo
do usuário, e derrubá-lo é uma perda que você não desfaz (skill `safe-operations`).

## Armadilhas

- **Diálogo modal trava tudo.** Nunca dispare `alert`, `confirm` ou `prompt`, nem clique em
  controle que os abra. O modal congela a extensão inteira e a sessão morre — não há como
  fechá-lo de fora. Para depurar, `read_console_messages`, nunca script que abre diálogo.
- **Permissão é por site**, configurada na extensão pelo próprio usuário. Navegação barrada
  não é bug do código: reporte `BLOQUEADO` com o campo `bloqueio` nomeando **a origem exata** a
  liberar (`http://localhost:5173`).
- **Aba do usuário não se reusa.** Só a aba criada por `tabs_create_mcp` é sua. Não navegue
  em aba existente, não feche aba que não abriu.
- **Serial, nunca paralelo.** É um navegador só. Dois agentes dirigindo ao mesmo tempo
  embaralham abas e invalidam a evidência.
- **Nada de headless, CI ou runner de navegador.** Este fluxo não usa binário
  headless; procurar um é turno jogado fora.
- **Página que ainda carrega.** Reveja com `find`/`get_page_text` antes de concluir que o
  elemento não existe — ausência pode ser timing, não bug.
