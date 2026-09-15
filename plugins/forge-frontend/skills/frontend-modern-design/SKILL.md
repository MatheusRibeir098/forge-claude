---
name: frontend-modern-design
description: Use ao aplicar tendências visuais modernas — glassmorphism, gradient mesh, bento grid, dark-first, tipografia oversized e efeitos (glow, shimmer, scroll reveal).
---

# Design Moderno & Efeitos Visuais (2026)

## Tendências de Design 2026

### 1. Glassmorphism (Vidro Fosco)
Painéis semi-transparentes com blur que criam profundidade.

```tsx
// Card glassmorphism
<div className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl p-6 shadow-lg">

// Navbar glassmorphism
<nav className="fixed top-0 w-full bg-slate-900/70 backdrop-blur-lg border-b border-white/10 z-50">

// Modal glassmorphism (dark mode)
<div className="bg-slate-800/80 backdrop-blur-2xl border border-slate-700/50 rounded-3xl p-8 shadow-2xl">
```

Regras: usar com moderação. Funciona melhor em dark mode, navbars e modais.

### 2. Gradient Mesh (Gradientes Orgânicos)
Gradientes multi-ponto com transições suaves tipo aurora boreal.

```tsx
// Background gradient mesh
<div className="relative overflow-hidden">
  <div className="absolute inset-0 bg-gradient-to-br from-violet-600/30 via-fuchsia-500/20 to-cyan-400/30 blur-3xl" />
  <div className="absolute top-1/4 -left-1/4 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl animate-pulse" />
  <div className="absolute bottom-1/4 -right-1/4 w-96 h-96 bg-cyan-500/20 rounded-full blur-3xl animate-pulse delay-1000" />
  <div className="relative z-10">{/* conteúdo */}</div>
</div>

// Gradient text
<h1 className="text-5xl font-extrabold bg-gradient-to-r from-violet-400 via-fuchsia-400 to-cyan-400 bg-clip-text text-transparent">
```

### 3. Bento Grid (Layout Assimétrico)
Grid inspirado em marmita japonesa — células de tamanhos variados.

```tsx
<div className="grid grid-cols-2 md:grid-cols-4 gap-4 auto-rows-[180px]">
  <div className="col-span-2 row-span-2 bg-white rounded-2xl p-6">Grande</div>
  <div className="bg-white rounded-2xl p-4">Pequeno</div>
  <div className="bg-white rounded-2xl p-4">Pequeno</div>
  <div className="col-span-2 bg-white rounded-2xl p-4">Médio</div>
</div>
```

### 4. Dark-First Design
Projetar primeiro em dark mode, depois adaptar pra light.

```tsx
// Paleta dark-first
<div className="bg-slate-950 text-white">
  <div className="bg-slate-900/50 border border-slate-800 rounded-2xl">
    <h2 className="text-white font-bold">Título</h2>
    <p className="text-slate-400">Descrição</p>
    <button className="bg-violet-600 hover:bg-violet-500 text-white rounded-xl px-6 py-2.5">
      CTA
    </button>
  </div>
</div>
```

### 5. Tipografia Oversized
Headlines grandes (48-120px) com impacto imediato.

```tsx
<h1 className="text-5xl md:text-7xl lg:text-8xl font-extrabold tracking-tight leading-none">
  Aprenda<br />
  <span className="bg-gradient-to-r from-violet-400 to-cyan-400 bg-clip-text text-transparent">
    Mais Rápido
  </span>
</h1>
```

## Efeitos CSS Modernos

### Glow / Neon
```tsx
// Botão com glow
<button className="bg-violet-600 hover:bg-violet-500 text-white rounded-xl px-6 py-3
  shadow-[0_0_20px_rgba(139,92,246,0.5)] hover:shadow-[0_0_30px_rgba(139,92,246,0.7)]
  transition-all duration-300">

// Card com borda glow
<div className="relative group">
  <div className="absolute -inset-0.5 bg-gradient-to-r from-violet-600 to-cyan-500 rounded-2xl blur opacity-30 group-hover:opacity-60 transition duration-300" />
  <div className="relative bg-slate-900 rounded-2xl p-6">Conteúdo</div>
</div>
```

### Hover com Profundidade
```tsx
// Card que "flutua" no hover
<div className="bg-white rounded-2xl p-6 border border-slate-200
  transition-all duration-300 ease-out
  hover:shadow-xl hover:shadow-slate-200/50 hover:-translate-y-1 hover:border-slate-300">

// Botão com press effect
<button className="transition-all duration-150 active:scale-[0.97] active:shadow-inner">
```

### Shimmer / Skeleton Loading
```tsx
// Shimmer effect
<div className="relative overflow-hidden bg-slate-200 rounded-xl">
  <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite]
    bg-gradient-to-r from-transparent via-white/60 to-transparent" />
</div>

// keyframe no tailwind.config.js:
// shimmer: { '100%': { transform: 'translateX(100%)' } }
```

### Scroll Reveal (CSS puro)
```tsx
// Elemento que aparece ao entrar no viewport
<div className="opacity-0 translate-y-8 transition-all duration-700
  [.visible_&]:opacity-100 [.visible_&]:translate-y-0">
```

Com Intersection Observer:
```tsx
useEffect(() => {
  const observer = new IntersectionObserver(
    (entries) => entries.forEach(e => e.isIntersecting && e.target.classList.add('visible')),
    { threshold: 0.1 }
  );
  document.querySelectorAll('[data-reveal]').forEach(el => observer.observe(el));
  return () => observer.disconnect();
}, []);
```

### Animated Border Gradient
```tsx
<div className="relative p-[1px] rounded-2xl bg-gradient-to-r from-violet-500 via-fuchsia-500 to-cyan-500
  animate-[spin_3s_linear_infinite] bg-[length:200%_200%]">
  <div className="bg-slate-900 rounded-2xl p-6">Conteúdo</div>
</div>
```

## Componentes Visuais Prontos

### Hero Section Moderna
```tsx
<section className="relative min-h-screen flex items-center justify-center overflow-hidden bg-slate-950">
  {/* Gradient mesh background */}
  <div className="absolute inset-0">
    <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-violet-600/20 rounded-full blur-[120px]" />
    <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-cyan-500/20 rounded-full blur-[100px]" />
  </div>
  {/* Content */}
  <div className="relative z-10 text-center px-4">
    <p className="text-violet-400 font-medium mb-4 tracking-wide uppercase text-sm">Plataforma de Estudos</p>
    <h1 className="text-5xl md:text-7xl font-extrabold text-white tracking-tight leading-none mb-6">
      Estude com<br />
      <span className="bg-gradient-to-r from-violet-400 to-cyan-400 bg-clip-text text-transparent">Inteligência</span>
    </h1>
    <p className="text-lg text-slate-400 max-w-xl mx-auto mb-8">Descrição curta e impactante.</p>
    <div className="flex gap-4 justify-center">
      <button className="px-8 py-3 bg-violet-600 hover:bg-violet-500 text-white font-medium rounded-xl
        shadow-[0_0_20px_rgba(139,92,246,0.4)] hover:shadow-[0_0_30px_rgba(139,92,246,0.6)] transition-all">
        Começar Agora
      </button>
      <button className="px-8 py-3 bg-white/5 hover:bg-white/10 text-white border border-white/10
        rounded-xl transition-all">
        Saiba Mais
      </button>
    </div>
  </div>
</section>
```

### Card Premium
```tsx
<div className="group relative">
  {/* Glow border */}
  <div className="absolute -inset-0.5 bg-gradient-to-r from-violet-600 to-cyan-500 rounded-2xl
    opacity-0 group-hover:opacity-40 blur transition duration-500" />
  {/* Card */}
  <div className="relative bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200
    dark:border-slate-800 transition-all duration-300 group-hover:-translate-y-0.5">
    <div className="w-10 h-10 bg-violet-100 dark:bg-violet-500/10 rounded-xl flex items-center justify-center mb-4">
      <Icon className="text-violet-600 dark:text-violet-400" size={20} />
    </div>
    <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Título</h3>
    <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">Descrição.</p>
  </div>
</div>
```

## Regras de Ouro

1. Menos é mais — 1-2 efeitos por página, não todos de uma vez
2. Performance primeiro — `transform` e `opacity` (GPU), nunca `width`/`height`
3. `prefers-reduced-motion` — sempre respeitar: `motion-reduce:transition-none`
4. Consistência — mesma paleta, mesmos raios de borda, mesmos espaçamentos
5. Mobile primeiro — efeitos pesados (blur, glow) podem ser reduzidos em mobile
6. Contraste — WCAG 4.5:1 mínimo, mesmo com glassmorphism

Content was rephrased for compliance with licensing restrictions.
Sources: [SERP Blocks Web Design Trends 2026](https://blocks.serp.co/blog/web-design-trends-2026), [TheEDigital Web Design Trends](https://www.theedigital.com/blog/web-design-trends), [MidRocket UI Design Trends 2026](https://midrocket.com/en/guides/ui-design-trends-2026/)
