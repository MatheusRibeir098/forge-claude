---
name: clean-code
description: Princípios de Clean Code. OBRIGATÓRIO ao escrever ou revisar qualquer código — nomenclatura, funções, DRY, KISS, tratamento de erros e organização.
---

# Clean Code — Skill Obrigatória

---

## Nomenclatura

```
// ❌ Ruim
const d = new Date();
const lista = getItems();
function proc(x) { ... }

// ✅ Bom
const dataAtual = new Date();
const produtosAtivos = getProdutosAtivos();
function calcularDesconto(preco) { ... }
```

- Nomes que revelam intenção
- Evitar abreviações (exceto universais: `id`, `url`)
- Booleanos começam com `is`, `has`, `should`, `can`
- Funções começam com verbos: `get`, `create`, `validate`, `calculate`

## Funções

- Fazem UMA coisa
- Máximo 20 linhas (preferir menos de 10)
- Máximo 3 parâmetros (usar objeto para mais)
- Sem efeitos colaterais a menos que explícito no nome

```
// ❌ Ruim
function processarPedido(pedido, usuario, config, logger, db) {
  // 50 linhas fazendo validação, cálculo, salvamento, log
}

// ✅ Bom
function validarPedido(pedido: Pedido): ResultadoValidacao { ... }
function calcularTotal(itens: Item[]): number { ... }
function salvarPedido(pedido: Pedido): Promise<void> { ... }
```

## DRY — Não Se Repita

- Extraia lógica repetida em funções
- Extraia padrões repetidos em utilitários
- MAS: não abstraia demais — duplicação é melhor que abstração errada

## KISS — Mantenha Simples

- Prefira legível a esperto
- Evite otimização prematura
- Evite abstrações desnecessárias

## Tratamento de Erros

```
// ❌ Ruim
function getUsuario(id) {
  try {
    return db.find(id);
  } catch (e) {
    console.log(e);
    return null;
  }
}

// ✅ Bom
function getUsuario(id: string): Usuario {
  const usuario = db.find(id);
  if (!usuario) throw new UsuarioNaoEncontradoError(id);
  return usuario;
}
```

- Use erros tipados/customizados
- Nunca engula exceções silenciosamente
- Falhe rápido e explicitamente

## Comentários

- Código deve ser auto-documentável
- Comentários explicam POR QUÊ, não O QUÊ
- Delete código comentado — git tem histórico

## Organização de Arquivos

- Um módulo/classe por arquivo
- Agrupe arquivos relacionados por feature, não por tipo
- Arquivos com menos de 200 linhas (preferir menos de 100)
