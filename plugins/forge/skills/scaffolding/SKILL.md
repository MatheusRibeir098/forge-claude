---
name: scaffolding
description: Use ao criar a estrutura inicial de um projeto do zero — checklist de setup (pastas, package.json, TS strict, Vite+Tailwind, proxy, .gitignore) e templates de tsconfig/vite.config.
---

# Scaffolding de Projetos

## Princípio
Ao criar um projeto do zero, a estrutura inicial define a qualidade de todo o resto. Invista
tempo no setup.

## Checklist de Setup

### 1. Inicialização
- [ ] Criar estrutura de pastas (`backend/`, `frontend/`)
- [ ] Inicializar `package.json` em cada workspace
- [ ] Instalar dependências core (pnpm)
- [ ] Configurar TypeScript (`tsconfig.json`) em strict mode
- [ ] Configurar bundler (`vite.config.ts`)
- [ ] Configurar Tailwind CSS
- [ ] Copiar o `.npmrc` do template (pré-aprova builds — evita `pnpm approve-builds` interativo)
- [ ] Criar `.gitignore`
- [ ] Criar `.env.example` com placeholders

### 2. Backend base
- [ ] Entry point (`index.ts`) com Express + CORS + JSON parser
- [ ] Conexão com banco (`database.ts`) com migrations inline
- [ ] Estrutura de rotas por feature
- [ ] Error handler global
- [ ] Script dev: `tsx watch src/index.ts`

### 3. Frontend base
- [ ] `App.tsx` com router
- [ ] Layout principal (header, sidebar, main)
- [ ] Tema/cores configurados no Tailwind
- [ ] API client (axios instance com baseURL)
- [ ] Página inicial funcional

## Templates de Configuração

### tsconfig.json (backend)
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src"]
}
```

### vite.config.ts (frontend com Tailwind v4)
```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': 'http://localhost:3001' } }
});
```

### Pré-aprovar build scripts (pnpm) sem interação
Dependências com scripts de build nativos (better-sqlite3, esbuild, etc.) exigem aprovação
no pnpm moderno. Para não travar num prompt interativo, liste-as no `package.json` do projeto:
```json
{
  "pnpm": {
    "onlyBuiltDependencies": ["better-sqlite3", "esbuild"]
  }
}
```
Assim `pnpm install` compila essas deps sem pedir `pnpm approve-builds`.

## Regras
- Sempre usar **pnpm** (não npm ou yarn)
- Sempre TypeScript strict mode
- Sempre configurar proxy no Vite pra evitar CORS em dev
- Sempre criar `.gitignore` antes do primeiro commit
- Nunca instalar dependências desnecessárias "por precaução"
