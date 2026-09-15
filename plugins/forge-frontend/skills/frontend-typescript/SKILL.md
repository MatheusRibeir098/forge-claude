---
name: frontend-typescript
description: Use ao escrever ou revisar código TypeScript — configuração strict, tipagem correta, enums vs union types, null safety e assertions seguras.
---

# Boas Práticas TypeScript

## Configuração Strict

```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true
  }
}
```

## Tipos

```ts
// ❌ Ruim
const dados: any = fetchDados();
function processar(item) { ... }

// ✅ Bom
const dados: DadosUsuario = fetchDados();
function processar(item: ItemPedido): ResultadoProcessamento { ... }
```

- Prefira `interface` para objetos, `type` para unions/intersections
- Nunca use `any` — use `unknown` se o tipo é desconhecido
- Use generics para código reutilizável
- Exporte tipos junto com as funções que os usam

## Enums vs Union Types

```ts
// ❌ Evitar
enum Status { Ativo, Inativo }

// ✅ Preferir
type Status = "ativo" | "inativo";
```

## Null Safety

```ts
// ❌ Ruim
function getNome(user: User) {
  return user.profile.name; // pode ser undefined
}

// ✅ Bom
function getNome(user: User): string | undefined {
  return user.profile?.name;
}
```

## Assertions

```ts
// ❌ Ruim
const el = document.getElementById("app") as HTMLDivElement;

// ✅ Bom
const el = document.getElementById("app");
if (!el) throw new Error("Elemento #app não encontrado");
```
