---
name: frontend-ui-design
description: Use ao criar ou reformular interfaces — princípios de UI/UX design moderno (hierarquia visual, espaçamento, cores, tipografia, cards, botões, feedback).
---

# UI Design Moderno — Princípios Obrigatórios

## Hierarquia Visual

Guie o olho do usuário com tamanho, peso, cor e espaçamento:

- Títulos: grande, bold, cor escura (`text-3xl font-bold text-slate-900`)
- Subtítulos: médio, semibold (`text-lg font-semibold text-slate-700`)
- Corpo: regular, cor suave (`text-sm text-slate-500`)
- Ações primárias: destaque com cor, tamanho e contraste
- Ações secundárias: menos destaque, outline ou ghost

```tsx
// ❌ Tudo com mesmo peso visual — usuário não sabe onde olhar
<h2 className="text-base text-gray-600">Título</h2>
<p className="text-base text-gray-600">Descrição</p>
<button className="text-base text-gray-600">Ação</button>

// ✅ Hierarquia clara
<h2 className="text-2xl font-bold text-slate-900">Título</h2>
<p className="text-sm text-slate-500 mt-1">Descrição</p>
<button className="mt-4 px-6 py-2.5 bg-blue-600 text-white font-medium rounded-xl">Ação</button>
```

## Espaçamento — Respire

Espaçamento generoso é o que separa UI amadora de profissional:

- Entre seções: `py-12` a `py-20`
- Entre cards: `gap-6` mínimo
- Padding interno de cards: `p-6` mínimo
- Entre título e conteúdo: `mb-2` a `mb-4`
- Entre grupos de elementos: `space-y-6`
- Nunca encoste elementos nas bordas — sempre padding

## Cores — Sistema Consistente

Use uma paleta restrita e com propósito:

- Background principal: `bg-slate-50` ou `bg-gray-50` (nunca branco puro)
- Cards: `bg-white` com sombra sutil
- Texto primário: `text-slate-900`
- Texto secundário: `text-slate-500`
- Accent/CTA: uma cor vibrante (ex: `blue-600`, `violet-600`, `indigo-600`)
- Sucesso: `emerald-500` | Erro: `red-500` | Warning: `amber-500`
- Bordas: `border-slate-200` (sutis, não pesadas)

## Tipografia

- Títulos de página: `text-3xl font-bold` ou `text-4xl font-extrabold`
- Títulos de seção: `text-xl font-semibold`
- Corpo: `text-sm` ou `text-base`, `leading-relaxed`
- Labels/captions: `text-xs font-medium text-slate-500 uppercase tracking-wide`
- Nunca use mais de 2-3 tamanhos de fonte por tela

## Cards Modernos

```tsx
// Card com profundidade e hover
<div className="bg-white rounded-2xl border border-slate-200/60 shadow-sm
  hover:shadow-md hover:border-slate-300 transition-all duration-200 p-6">
```

- Bordas arredondadas generosas: `rounded-xl` ou `rounded-2xl`
- Sombras sutis: `shadow-sm` base, `shadow-md` no hover
- Transições suaves: `transition-all duration-200`

## Botões

```tsx
// Primário
<button className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white
  font-medium rounded-xl shadow-sm hover:shadow transition-all duration-150">

// Secundário
<button className="px-6 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700
  font-medium rounded-xl transition-all duration-150">

// Ghost
<button className="px-4 py-2 text-slate-500 hover:text-slate-700
  hover:bg-slate-100 rounded-lg transition-all duration-150">
```

## Ícones

- Tamanho proporcional ao texto: `size={16}` com `text-sm`, `size={20}` com `text-base`
- Cor mais suave que o texto: `text-slate-400` ou cor do accent
- Sempre com `gap-2` entre ícone e texto
- Nunca ícone sozinho sem `aria-label`

## Feedback Visual

- Loading: skeleton ou spinner com `animate-pulse` / `animate-spin`
- Hover: mudança de cor/sombra com `transition-all duration-150`
- Focus: `focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none`
- Active: `active:scale-[0.98]` para botões
- Empty states: ilustração + texto + CTA, nunca tela vazia
