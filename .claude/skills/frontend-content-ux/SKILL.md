---
name: frontend-content-ux
description: Use ao exibir conteúdo longo (educativo, documentação) — padrões de UX com cards minimizados, modo foco, slides, progresso persistente e scroll-to-top.
---

# UX para Conteúdo Longo

## Problema
Conteúdo educativo/documentação longo renderizado como textão é difícil de navegar e desmotivante.

## Solução: Cards Minimizados + Modo Foco

### Cards Minimizados (lista)
Cada bloco de conteúdo aparece como card compacto:
- Ícone + título descritivo
- Barra de progresso (barrinhas coloridas por seção)
- Status: "X/Y lidas" ou "✓ Concluído"
- Clicável → expande para modo foco

### Modo Foco (expandido)
Ao clicar, o card expande ocupando quase a tela:
- Botão "Voltar à lista" no topo
- Header fixo: título + progresso + "Marcar como lida"
- Conteúdo scrollável contido (`overflow-y-auto overscroll-contain`)
- Navegação fixa no rodapé: Anterior / dots / Próximo

### Navegação em Slides
Quebrar conteúdo por `## ` (H2) — cada seção vira um slide:
```ts
function splitByH2(markdown: string): { title: string; content: string }[] {
  // Iterar linhas, detectar ## , acumular seções
}
```

### Progresso Persistente
```ts
// Salvar no localStorage por subject
const storageKey = 'progress-' + subjectId;
const [readSections, setReadSections] = useState<Set<string>>(() => {
  const saved = localStorage.getItem(storageKey);
  return saved ? new Set(JSON.parse(saved)) : new Set();
});

// Auto-marcar como lido ao navegar
function goToSlide(itemId, index, total) {
  // Marcar slide ATUAL como lido antes de mudar
  const currentKey = itemId + '-' + currentIndex;
  setReadSections(prev => new Set(prev).add(currentKey));
  // Navegar
  setCurrentSlides(prev => ({ ...prev, [itemId]: clamp(index, 0, total - 1) }));
}
```

### Barra de Progresso Visual
```tsx
<div className="flex gap-1">
  {sections.map((_, j) => (
    <button key={j} onClick={() => goToSlide(itemId, j, total)}
      className={`h-1.5 rounded-full flex-1 transition-all ${
        j === current ? 'bg-brand-500'
        : readSections.has(key) ? 'bg-emerald-400'
        : 'bg-slate-200 dark:bg-slate-700'
      }`} />
  ))}
</div>
```

## Títulos Descritivos
Nomes de arquivo são ruins como título. Estratégia de fallback:
1. Primeiro keyTopic do resumo gerado
2. Título da primeira seção H2 do conteúdo
3. cleanTitle() que extrai partes legíveis de nomes de arquivo
4. "Aula X" como último recurso

## Opções de Conteúdo
Deixar o usuário escolher o que gerar (checkboxes):
- Salvar preferências no localStorage por subject
- Esconder abas não selecionadas na página de resultado
- Backend pula gerações desmarcadas (economia de tempo)

## Botão Scroll-to-Top
```tsx
// Aparece ao rolar 400px+
const [show, setShow] = useState(false);
useEffect(() => {
  const onScroll = () => setShow(window.scrollY > 400);
  window.addEventListener('scroll', onScroll);
  return () => window.removeEventListener('scroll', onScroll);
}, []);

{show && (
  <button onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
    className="fixed bottom-6 right-6 z-50 p-3 bg-brand-500 text-white rounded-full shadow-lg">
    <ArrowUp size={20} />
  </button>
)}
```
