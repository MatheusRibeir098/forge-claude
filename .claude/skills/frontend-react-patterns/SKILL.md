---
name: frontend-react-patterns
description: Use ao criar ou refatorar componentes React — composição, separação lógica/apresentação, variantes, conditional rendering, keys e acessibilidade.
---

# React Patterns para UI

## Composição de Componentes

```tsx
// ❌ Componente monolítico com props demais
<Card title="..." subtitle="..." icon={...} badge="..." onClick={...} footer={...} />

// ✅ Composição — flexível e legível
<Card onClick={...}>
  <Card.Header>
    <Card.Icon icon={BookOpen} />
    <Card.Title>...</Card.Title>
  </Card.Header>
  <Card.Body>...</Card.Body>
  <Card.Footer>...</Card.Footer>
</Card>
```

## Componentes de Apresentação vs Lógica

```tsx
// Hook encapsula lógica
function useQuiz(subjectId: number) {
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Answer[]>([]);
  // ... toda a lógica
  return { current, answers, handleAnswer, handleNext, isFinished };
}

// Componente só renderiza
function QuizView({ quiz, onAnswer, onNext }: QuizViewProps) {
  return (/* JSX puro, sem lógica de negócio */);
}
```

## Props com Variantes (Pattern de Design System)

```tsx
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

const styles = {
  variant: {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white shadow-sm',
    secondary: 'bg-slate-100 hover:bg-slate-200 text-slate-700',
    ghost: 'hover:bg-slate-100 text-slate-600',
    danger: 'bg-red-600 hover:bg-red-700 text-white',
  },
  size: {
    sm: 'px-3 py-1.5 text-sm rounded-lg',
    md: 'px-5 py-2.5 text-sm rounded-xl',
    lg: 'px-8 py-3 text-base rounded-xl',
  },
} as const;
```

## Conditional Rendering Limpo

```tsx
// ❌ Ternários aninhados
{loading ? <Spinner /> : error ? <Error /> : data ? <Content /> : <Empty />}

// ✅ Early return ou mapa de estados
if (loading) return <Skeleton />;
if (error) return <ErrorState message={error.message} />;
if (!data?.length) return <EmptyState />;
return <ContentList data={data} />;
```

## Listas com Keys Corretas

```tsx
// ❌ Index como key
{items.map((item, i) => <Card key={i} />)}

// ✅ ID estável como key
{items.map((item) => <Card key={item.id} />)}
```

## Forwarding de className

```tsx
// Permitir customização externa sem quebrar estilos base
function Card({ className, children, ...props }: CardProps) {
  return (
    <div className={`bg-white rounded-2xl border border-slate-200 p-6 ${className ?? ''}`} {...props}>
      {children}
    </div>
  );
}
```

## Acessibilidade Obrigatória

- Botões com ícone: sempre `aria-label`
- Imagens: sempre `alt`
- Inputs: sempre `<label>` associado ou `aria-label`
- Modais: `role="dialog"`, `aria-modal="true"`, focus trap
- Contraste mínimo: 4.5:1 para texto normal, 3:1 para texto grande
- Elementos interativos: `focus-visible:ring-2` para navegação por teclado
- Listas: usar `<ul>/<ol>` semântico, não `<div>` com role
