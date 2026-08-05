---
name: frontend-performance
description: Use ao otimizar performance de frontend React e acessibilidade — memoização, code splitting, virtualização, data fetching, Core Web Vitals e WCAG 2.2.
---

# Frontend Performance & Patterns (2026)

## Otimização de Performance React

### 1. Memoização
- `React.memo` — evita re-render quando props não mudam
- `useMemo` — cacheia resultado de computação cara
- `useCallback` — estabiliza referência de função (essencial com React.memo)
- React Compiler (React 19+) — aplica memoização automaticamente no build

### 2. Code Splitting & Lazy Loading
- `React.lazy` + `Suspense` — carrega componentes sob demanda
- Splitting por rota: cada página é um chunk separado
- Dynamic imports para libs pesadas (PDF viewers, editores, charts)
- Impacto direto no LCP (Largest Contentful Paint)

### 3. Gerenciamento de Estado
- Estado local primeiro — só suba pra global se necessário
- Context API: dividir em contextos focados (UserCtx, ThemeCtx, NotificationCtx)
- Zustand/Jotai com seletores — componente só re-renderiza quando seu slice muda
- `useTransition` — marca updates como não-urgentes, mantém UI responsiva
- `useDeferredValue` — adia valor pra priorizar updates urgentes

### 4. Virtualização de Listas
- `react-window` (~6KB) — listas simples, tamanho fixo/variável
- `@tanstack/virtual` — tabelas complexas, alturas dinâmicas, sticky headers
- Regra: < 100 itens não precisa; > 100 considere; > 1000 obrigatório

### 5. Data Fetching
- TanStack Query / SWR — cache, dedup, revalidação automática
- `staleTime` pra evitar refetch desnecessário
- Fetching paralelo com `Promise.all` quando requests são independentes
- Debounce em search inputs (300ms padrão)

### 6. Bundle & Assets
- Named imports em vez de namespace imports (tree shaking)
- WebP/AVIF para imagens (25-50% menor que PNG/JPEG)
- Lazy loading de imagens off-screen
- CSS `transform`/`opacity` para animações (GPU compositor thread)
- `contain: layout style paint` para isolar reflows

### 7. Web Workers
- Mover computação pesada pra background thread
- Main thread livre pra interação do usuário
- Usar `new Worker(new URL('./worker.ts', import.meta.url))`

## Core Web Vitals (metas 2026)
- LCP < 2.5s — code splitting, otimização de imagens
- INP < 200ms — memoização, web workers, useTransition
- CLS < 0.1 — dimensões explícitas em imagens, skeleton loaders

## Acessibilidade (WCAG 2.2 AA — obrigatório em 2026)

### Princípios POUR
- Perceivable: alt text, contraste 4.5:1, legendas em vídeo
- Operable: tudo navegável por teclado, focus visible, sem armadilhas de foco
- Understandable: labels claros, mensagens de erro descritivas, linguagem simples
- Robust: HTML semântico, ARIA roles corretos, funciona com screen readers

### React específico
- HTML semântico: `<button>` em vez de `<div onClick>`
- `aria-label`, `aria-describedby`, `aria-live` para conteúdo dinâmico
- Focus management em SPAs: anunciar mudanças de rota
- `<details>/<summary>` para accordions nativos
- Skip links para navegação por teclado
- Testar com axe-core, Lighthouse, NVDA/VoiceOver

### Compliance 2026
- EAA (EU): em vigor desde jun/2025 — multas até €500.000
- ADA Title II (US): deadline abr/2026 — WCAG 2.1 AA
- WCAG 3.0: previsto 2027-2028

## Patterns React Modernos

### Compound Components
```tsx
<Select>
  <Select.Trigger>Escolha</Select.Trigger>
  <Select.Options>
    <Select.Option value="a">A</Select.Option>
  </Select.Options>
</Select>
```

### Custom Hooks (separar lógica de UI)
```tsx
function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
```

### Error Boundaries
```tsx
class ErrorBoundary extends Component {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) return <FallbackUI />;
    return this.props.children;
  }
}
```

Content was rephrased for compliance with licensing restrictions.
Sources: [TurboDocx React Performance Guide](https://www.turbodocx.com/blog/react-performance-optimization), [CodeWithSeb Accessibility Guide](https://codewithseb.com/blog/web-accessibility-2026-eaa-ada-wcag-guide), [Syncfusion Frontend Trends 2026](https://syncfusion.com/blogs/post/frontend-development-trends-2025)
