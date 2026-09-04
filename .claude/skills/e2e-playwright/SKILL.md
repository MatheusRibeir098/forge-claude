---
name: e2e-playwright
description: Use ao rodar testes end-to-end com Playwright — subir servidores em background, executar specs, capturar screenshots e derrubar os servidores ao final.
---

# E2E com Playwright

## Setup de servidores para teste

Servidores de longa duração (backend, frontend dev server) devem rodar em **background**, nunca travando a sessão em foreground. Use a ferramenta Bash com `run_in_background` para cada servidor e aguarde ficarem prontos antes de testar.

```bash
# Subir backend em background (a partir de <projeto>/backend)
pnpm dev

# Subir frontend em background (a partir de <projeto>/frontend)
pnpm dev

# Aguardar servidores ficarem prontos (health-check)
curl -s http://localhost:3001/api/subjects > /dev/null && echo "Backend OK"
curl -s http://localhost:5173 > /dev/null && echo "Frontend OK"
```

## Executar testes E2E

```bash
cd <projeto>/e2e
npx playwright test <arquivo-de-teste>.spec.ts --headed
```

Se não existir teste específico, criar um inline:
```bash
cd <projeto>/e2e
cat > test-fix.spec.ts << 'EOF'
import { test, expect } from '@playwright/test';
test('descrição do teste', async ({ page }) => {
  await page.goto('http://localhost:5173');
  // assertions específicas do bug corrigido
});
EOF
npx playwright test test-fix.spec.ts
```

## Derrubar servidores após teste

Encerre os processos em background pela porta que ocupam:

```bash
kill $(lsof -t -i:3001) 2>/dev/null   # backend
kill $(lsof -t -i:5173) 2>/dev/null   # frontend
```

## Boas práticas

- Aguarde elementos com `await page.waitForSelector()` antes de interagir
- Use `page.waitForResponse()` para aguardar chamadas de API
- Screenshots: salve em `projects/<nome-do-projeto>/.forge/screenshots/` (ex: `await page.screenshot({ path: 'projects/<nome-do-projeto>/.forge/screenshots/fail.png' })`). A pasta não é apagada.
- **Screenshots: máximo 5 por tarefa, sem `fullPage`** (só o viewport; para algo abaixo da
  dobra, role até lá e capture). O teto não é economia — imagem é cobrada por área e deu ~1%
  do consumo do Forge quando medido; ele existe para manter o foco no que a tarefa mudou, e
  `fullPage` gera imagem redimensionada e ilegível. Quem analisa as imagens é o `tester`,
  dentro do contexto dele — o Forge lê apenas a descrição textual no JSON de retorno.
- Timeout padrão: 30s. Se precisar mais, use `test.setTimeout(60000)`
- Viewport desktop 1280x720; mobile 375x667 **apenas quando a tarefa mexeu no layout**
