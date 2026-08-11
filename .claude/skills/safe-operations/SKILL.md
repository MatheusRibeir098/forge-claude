---
name: safe-operations
description: Use antes de ações que possam derrubar servidores/processos em andamento, antes de analisar uma branch, e ao rodar comandos cujo output pode ser grande — verificar processos ativos, dar git pull e filtrar output na fonte.
---

# Operações Seguras — Proteção de Processos em Andamento

## Regra OBRIGATÓRIA (Forge e subagentes)

ANTES de qualquer ação que possa derrubar ou afetar servidores/processos rodando:

1. **Verifique se há processos ativos:**
```bash
# Verificar se backend está rodando
lsof -i :3001 2>/dev/null && echo "⚠️ Backend rodando na porta 3001"
lsof -i :5173 2>/dev/null && echo "⚠️ Frontend rodando na porta 5173"
```

2. **Se houver processos ativos, PERGUNTE ao usuário antes de continuar:**
```
⚠️ Detectei processos em andamento:
- Backend rodando na porta 3001
- Frontend rodando na porta 5173

Posso continuar? Isso pode derrubar os processos acima.
Aguardando confirmação...
```

3. **Só prossiga após confirmação explícita do usuário.**

## Ações que EXIGEM essa verificação

- Reiniciar servidores (matar o processo em background que roda o dev server)
- Modificar arquivos do backend que causam hot-reload (`src/**/*.ts`)
- Rodar `pnpm install` (pode travar o processo)
- Alterar `package.json` ou `tsconfig.json`
- Qualquer `kill`, `pkill`, `killall`
- Rodar migrations ou scripts que alteram o banco de dados

## Ações que NÃO precisam de verificação

- Ler arquivos (Read, cat, grep)
- Modificar arquivos de frontend (hot-reload não derruba backend)
- Criar arquivos novos
- Rodar testes

---

## Regra OBRIGATÓRIA: filtre o output na fonte

Todo comando que você roda entra no contexto e é reenviado a cada turno seguinte. Um
`pnpm install` verboso ou um `git log` completo custa mais que a tarefa que você está fazendo.
Corte **antes** de o output existir, não depois:

| Em vez de | Use |
|---|---|
| `git log` | `git log --oneline -20` |
| `git diff` | `git diff --stat` primeiro; o diff completo só do arquivo que importa |
| `pnpm install` | `pnpm install 2>&1 \| tail -5` |
| `pnpm build` / `tsc` | `... 2>&1 \| tail -30` (o erro está no fim) |
| `find .` | `find src -name "*.ts" -not -path "*/node_modules/*"` |
| `cat arquivo-grande` | `Read` com `offset`/`limit`, ou `grep -n` no trecho |
| `gh pr view` | `gh pr view --json title,body --jq ...` |
| Rodar a suite inteira | Só o teste da tarefa atual |

Nunca use `cat` em lockfile, build, `node_modules` ou binário. Se precisa saber se algo
existe, `test -f` responde em 1 linha; `ls` de uma pasta grande, não.

---

## Regra OBRIGATÓRIA: Pull antes de analisar branch

**SEMPRE** fazer `git pull` de uma branch antes de analisá-la ou compará-la. Nunca trabalhar com código local desatualizado.

```bash
# ANTES de qualquer análise ou diff
git checkout <branch> && git pull origin <branch>
```

Isso evita comparações incorretas e conclusões erradas baseadas em código que já foi atualizado no remote.
