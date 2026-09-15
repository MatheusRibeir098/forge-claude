---
name: frontend-responsive
description: Use ao criar ou ajustar layouts — design responsivo mobile-first com Tailwind (grids, tipografia e espaçamento que escalam por breakpoint).
---

# Design Responsivo — Mobile First

## Filosofia

Comece pelo mobile, adicione complexidade para telas maiores. Tailwind é mobile-first por padrão: classes sem prefixo = mobile, `sm:` = 640px+, `md:` = 768px+, `lg:` = 1024px+, `xl:` = 1280px+.

## Layout Patterns

```tsx
// Grid responsivo: 1 col mobile → 2 cols tablet → 3 cols desktop
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">

// Sidebar: stack no mobile, side-by-side no desktop
<div className="flex flex-col lg:flex-row gap-6">
  <aside className="w-full lg:w-64 lg:shrink-0">...</aside>
  <main className="flex-1 min-w-0">...</main>
</div>

// Container com max-width e padding responsivo
<div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
```

## Tipografia Responsiva

```tsx
// Títulos que escalam
<h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold">

// Texto que respira
<p className="text-sm sm:text-base leading-relaxed">
```

## Componentes Adaptativos

```tsx
// Botões: full-width no mobile, auto no desktop
<button className="w-full sm:w-auto px-6 py-2.5 ...">

// Tabs: scroll horizontal no mobile, flex no desktop
<div className="flex overflow-x-auto sm:overflow-visible gap-1 -mx-4 px-4 sm:mx-0 sm:px-0">

// Modal: fullscreen no mobile, centered no desktop
<div className="fixed inset-0 sm:inset-auto sm:top-1/2 sm:left-1/2
  sm:-translate-x-1/2 sm:-translate-y-1/2 sm:max-w-lg sm:rounded-2xl">

// Esconder/mostrar elementos por breakpoint
<span className="hidden sm:inline">Texto completo</span>
<span className="sm:hidden">Curto</span>
```

## Espaçamento Responsivo

```tsx
// Padding de seção que escala
<section className="py-8 sm:py-12 lg:py-16">

// Gap que escala
<div className="grid gap-4 sm:gap-6 lg:gap-8">
```

## Regras

- Nunca use larguras fixas em px para containers — use `max-w-*` + `w-full`
- Nunca esconda conteúdo importante no mobile — reorganize, não esconda
- Teste em 320px (mobile pequeno), 768px (tablet), 1024px+ (desktop)
- Imagens: `w-full` + `max-w-*` + `object-cover`
- Tabelas: `overflow-x-auto` wrapper no mobile
- Touch targets: mínimo `h-10 w-10` (44px) para botões/links no mobile
