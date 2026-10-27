---
name: frontend-dark-mode
description: Use ao adicionar tema escuro — implementação de dark mode com Tailwind CSS (setup, hook useTheme, paleta de cores e armadilhas).
---

# Dark Mode com Tailwind CSS

## Setup

```js
// tailwind.config.js
export default {
  darkMode: 'class', // toggle via classe no <html>
  // ...
}
```

## Hook useTheme

```tsx
function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('theme', theme);
  }, [theme]);

  return { theme, toggle: () => setTheme(t => t === 'dark' ? 'light' : 'dark') };
}
```

## Padrões de Cores

| Elemento | Light | Dark |
|----------|-------|------|
| Background | `bg-slate-50` | `dark:bg-slate-900` |
| Card | `bg-white` | `dark:bg-slate-800` |
| Borda | `border-slate-200` | `dark:border-slate-700` |
| Texto primário | `text-slate-900` | `dark:text-white` |
| Texto secundário | `text-slate-500` | `dark:text-slate-400` |
| Input | `bg-white border-slate-200` | `dark:bg-slate-800 dark:border-slate-700` |
| Hover | `hover:bg-slate-100` | `dark:hover:bg-slate-800` |

## Armadilhas

- Cores hardcoded `[#hex]` NÃO respondem ao `dark:` — usar classes Tailwind semânticas
- `dark:prose-invert` só funciona se as cores do prose forem semânticas
- Scrollbar: precisa de CSS custom `.dark ::-webkit-scrollbar-thumb`
- `::selection`: precisa de `.dark ::selection` separado
- Mermaid: detectar dark mode e trocar tema na inicialização
- Focus rings: adicionar `dark:focus:ring-offset-slate-900`

## Checklist

- [ ] `darkMode: 'class'` no tailwind.config
- [ ] Hook useTheme com localStorage + prefers-color-scheme
- [ ] Toggle no Header (Sun/Moon icons)
- [ ] Body: `dark:bg-slate-900 dark:text-slate-100`
- [ ] Todos os componentes UI com `dark:` variants
- [ ] Todas as páginas com `dark:bg-slate-900`
- [ ] Prose/markdown com classes semânticas + `dark:prose-invert`
- [ ] Inputs/selects com dark variants
- [ ] Scrollbar e selection customizados
