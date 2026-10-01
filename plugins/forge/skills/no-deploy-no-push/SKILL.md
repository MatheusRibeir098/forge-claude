---
name: no-deploy-no-push
description: Use antes de qualquer deploy, git push ou criação de repositório — o que exige autorização explícita do usuário, o que ignorar no commit e commits em português.
---

# Regras de Deploy e Git

## ⛔ NUNCA FAZER por conta própria (sem o usuário mandar explicitamente)

### Deploy
- **NUNCA** executar deploy de qualquer tipo por iniciativa própria: infraestrutura como código (apply, deploy, destroy), container (push para registry remoto), funções sem servidor, comandos de CLI de cloud que criem, modifiquem ou apaguem recursos, ou aplicação em cluster remoto

### Git Push
- **NUNCA** executar `git push` por iniciativa própria (nenhuma variação: `--force`, `--tags`, nada)

## ✅ QUANDO O USUÁRIO MANDAR EXPLICITAMENTE

Se o usuário disser **"faça o push"**, **"faça o deploy"**, **"faça commit, push e deploy"** — execute sem pedir confirmação extra.

Exemplos de comandos explícitos que autorizam a ação:
- "Faça o push" → executa `git push`
- "Faça o deploy" → executa o deploy do projeto
- "Faça commit, push e deploy" → executa os três em sequência

## ⛔ NUNCA commitar arquivos desnecessários

Quando o usuário pedir para **"subir para o GitHub"** ou **"criar repositório"**, commitar APENAS o que é necessário para o projeto funcionar.

### Sempre ignorar (adicionar ao .gitignore antes do primeiro commit):
- `.claude/` — configurações internas do Forge/Claude Code (skills, settings)
- `e2e/` e artefatos de validação do `claude-in-chrome` — testes locais de desenvolvimento
- `.forge/` — evidências e artefatos internos do forge (`projects/<nome-do-projeto>/.forge/`)
- `prompt.md` — spec/prompt interno do forge
- `orchestration/` — logs e sinais do forge-loop
- `*.log`, `run.sh`, `setup.sh`, `clean-logs.sh` — scripts de orquestração local

### Regra geral
> Repositório público = apenas código-fonte, assets do produto, README e configurações de build. Nada de infraestrutura interna de desenvolvimento.

---

## ✅ COMMITS SEMPRE EM PORTUGUÊS

Todas as mensagens de commit devem ser escritas em **português brasileiro**.

```bash
# ✅ Correto
git commit -m "feat: adiciona página de histórico"
git commit -m "fix: corrige validação do formulário"
git commit -m "docs: atualiza README com instruções de uso"
git commit -m "chore: remove arquivos desnecessários do repositório"

# ❌ Errado
git commit -m "feat: add history page"
git commit -m "fix: form validation"
```

Prefixos convencionais (em inglês) são permitidos — `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `style:`, `test:` — mas a **descrição** deve ser sempre em português.

---

## ✅ O QUE DEVE FAZER SEM PRECISAR DE AUTORIZAÇÃO

### Git — Operações locais sempre permitidas
```bash
git init
git add .
git commit -m "mensagem"
git branch <nome>
git checkout <branch>
git merge <branch>
git log
git status
git diff
git diff --staged
git diff HEAD~1
git log --oneline -5
```

### Deploy — Sempre mostrar diff antes
- Criar arquivos de configuração (Dockerfile, arquivos de infraestrutura como código) → OK
- Rodar `docker build` localmente → OK
- Gerar artefatos de build (`pnpm build`, `npm run build`) → OK
- Rodar o diff/plano da ferramenta de IaC (apenas leitura) → OK

## ✅ OBRIGATÓRIO: Mostrar diff antes de deploy

### Git diff
```bash
git diff
git diff --staged
git log --oneline -5
```

### Diff de infraestrutura
Use o comando de diff/plano da sua ferramenta de IaC: ele mostra o que seria criado, alterado ou deletado, sem aplicar nada.

### Fluxo obrigatório quando há infraestrutura
1. Fazer as alterações no código
2. Rodar o diff/plano da ferramenta de IaC e mostrar ao usuário
3. Aguardar o usuário mandar executar o deploy
