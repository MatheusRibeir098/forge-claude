---
name: frontend-tailwind
description: Use ao estilizar componentes frontend — boas práticas de organização de classes, componentização, responsividade e dark mode com Tailwind CSS.
---

# Boas Práticas Tailwind CSS

## Organização de Classes

```tsx
// ❌ Ruim — classes desorganizadas
<div className="text-red-500 flex p-4 bg-white mt-2 rounded-lg shadow-md items-center">

// ✅ Bom — agrupadas por categoria (layout → espaçamento → visual → texto)
<div className="flex items-center mt-2 p-4 bg-white rounded-lg shadow-md text-red-500">
```

## Componentização

```tsx
// ❌ Ruim — classes repetidas em vários lugares
<button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
<button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">

// ✅ Bom — extrair em componente
function BotaoPrimario({ children, ...props }) {
  return (
    <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700" {...props}>
      {children}
    </button>
  );
}
```

## Responsividade

- Mobile-first: comece sem prefixo, adicione `sm:`, `md:`, `lg:`
- Use `container` com `mx-auto` para centralizar
- Teste em múltiplos breakpoints

## Dark Mode

- Use `dark:` prefix
- Configure `darkMode: 'class'` no tailwind.config
