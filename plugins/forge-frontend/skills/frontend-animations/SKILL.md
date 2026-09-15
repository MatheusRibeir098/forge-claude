---
name: frontend-animations
description: Use ao criar componentes interativos — micro-interações e animações sutis com Tailwind CSS (transições, keyframes, stagger, loading states).
---

# Animações e Micro-Interações

## Princípio

Animações devem ser sutis, rápidas e com propósito. Guiam atenção, dão feedback e criam sensação de qualidade. Nunca decorativas sem função.

## Transições Base (Tailwind puro)

```tsx
// Hover em cards — sombra + leve elevação
<div className="transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5">

// Hover em botões — cor + escala sutil
<button className="transition-all duration-150 hover:bg-blue-700 active:scale-[0.98]">

// Fade in ao aparecer
<div className="animate-in fade-in duration-300">

// Slide up ao aparecer
<div className="animate-in slide-in-from-bottom-2 duration-300">
```

## Keyframes Customizados (tailwind.config.js)

```js
// Adicionar ao theme.extend
keyframes: {
  'fade-in': {
    '0%': { opacity: '0', transform: 'translateY(8px)' },
    '100%': { opacity: '1', transform: 'translateY(0)' },
  },
  'slide-up': {
    '0%': { opacity: '0', transform: 'translateY(16px)' },
    '100%': { opacity: '1', transform: 'translateY(0)' },
  },
  'scale-in': {
    '0%': { opacity: '0', transform: 'scale(0.95)' },
    '100%': { opacity: '1', transform: 'scale(1)' },
  },
},
animation: {
  'fade-in': 'fade-in 0.3s ease-out',
  'slide-up': 'slide-up 0.4s ease-out',
  'scale-in': 'scale-in 0.2s ease-out',
},
```

## Staggered Animations (entrada sequencial)

```tsx
// Cards que aparecem um após o outro
{items.map((item, i) => (
  <div
    key={item.id}
    className="animate-fade-in"
    style={{ animationDelay: `${i * 75}ms`, animationFillMode: 'backwards' }}
  >
    ...
  </div>
))}
```

## Loading States

```tsx
// Skeleton com pulse
<div className="animate-pulse space-y-4">
  <div className="h-4 bg-slate-200 rounded-lg w-3/4" />
  <div className="h-4 bg-slate-200 rounded-lg w-1/2" />
  <div className="h-32 bg-slate-200 rounded-xl" />
</div>

// Spinner
<div className="h-5 w-5 border-2 border-slate-300 border-t-blue-600 rounded-full animate-spin" />
```

## Regras

- Duração: 150ms para hover, 200-300ms para entrada, 150ms para saída
- Easing: `ease-out` para entradas, `ease-in` para saídas
- Nunca anime layout properties (width, height) — use transform e opacity
- Respeite `prefers-reduced-motion`: `motion-reduce:transition-none`
- Máximo 1-2 animações simultâneas por viewport — mais que isso é ruído
