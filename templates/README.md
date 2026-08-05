# templates/

Arquivos-base usados pelo hub `/forge` e pelo subagente `dev` ao criar um projeto do zero.

- **`prompt.template.md`** — estrutura do `prompt.md` gerado pela skill `meta-prompt`.
- **`.npmrc`** — conveniências de dev; copiar para a raiz de cada projeto novo.

## Scaffolding padrão (referência)

O `dev` gera a estrutura via CLIs oficiais (não há árvore duplicada aqui):

```bash
# Frontend
pnpm create vite <nome> --template react-ts
cd <nome> && pnpm add -D tailwindcss @tailwindcss/vite

# Backend
mkdir backend && cd backend && pnpm init
pnpm add express cors better-sqlite3
pnpm add -D typescript @types/express @types/cors @types/better-sqlite3 tsx
```

Detalhes de configuração (tsconfig, vite.config, proxy, pré-aprovação de builds) estão na
skill `scaffolding`. Estrutura de pastas na skill e no `dev`.

## Layout de um projeto gerado

```
projects/<nome>/
├── prompt.md              # spec (gerada pelo hub)
├── frontend/  backend/    # código (escrito pelo dev)
└── .forge/
    ├── tasks.md           # backlog de tarefas atômicas
    ├── progress.md        # log de cada ciclo (dev + tester)
    └── screenshots/       # prints do tester
```
