---
name: lessons-learned
description: Lições aprendidas em projetos reais — erros comuns, armadilhas e soluções testadas em produção (async, SQLite, upload, renderização, UX, processo).
---

# Lições Aprendidas — Base de Conhecimento

## Processamento Assíncrono

### Try/catch isolados por operação
Quando múltiplas operações independentes rodam em sequência, CADA UMA deve ter seu próprio try/catch. Se uma falha, as outras continuam.
```
// ❌ Um erro derruba tudo
try {
  await operacao1();
  await operacao2(); // se falhar, operacao3 nunca roda
  await operacao3();
} catch (e) { ... }

// ✅ Cada uma independente
try { await operacao1(); } catch (e) { log(e); }
try { await operacao2(); } catch (e) { log(e); }
try { await operacao3(); } catch (e) { log(e); }
```

### Promise.allSettled vs Promise.all
- `Promise.all` — falha se QUALQUER promise falhar. Usar quando todas são obrigatórias.
- `Promise.allSettled` — espera TODAS terminarem, retorna status individual. Usar quando são independentes.
- CUIDADO: nem toda ferramenta suporta execução paralela (ex: CLIs que compartilham stdout).

### Progresso em processamento longo
- Sempre mostrar estimativa de tempo baseada em dados REAIS do backend (timestamps), não do frontend
- Datas UTC do banco (SQLite `datetime('now')`) precisam de `+ 'Z'` ao parsear no JS: `new Date(dateStr + 'Z')`
- Polling com `refetchInterval` do TanStack Query funciona bem para acompanhar progresso

## SQLite

### Migrations em bancos existentes
`CREATE TABLE IF NOT EXISTS` NÃO altera tabelas existentes. Para adicionar colunas:
```js
const columns = db.prepare("PRAGMA table_info(tableName)").all();
if (!columns.some(c => c.name === 'new_column')) {
  db.exec("ALTER TABLE tableName ADD COLUMN new_column TEXT DEFAULT 'value'");
}
```

### CHECK constraints
SQLite não suporta `ALTER TABLE ... ALTER COLUMN`. Se precisa mudar um CHECK constraint, use valores compatíveis com o constraint existente em vez de tentar alterá-lo.

## Upload de Arquivos

### FormData com Axios
NUNCA setar `Content-Type: multipart/form-data` manualmente. O Axios gera o boundary automaticamente ao detectar FormData.
```js
// ❌ Quebra o upload
api.post('/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

// ✅ Axios detecta FormData e seta o header correto
api.post('/upload', formData);
```

### Input file + React state
Ao ler `e.target.files` e limpar o input depois, copiar os arquivos ANTES de limpar:
```js
// ❌ FileList é esvaziado antes do React processar
if (e.target.files) setFiles(prev => [...prev, ...Array.from(e.target.files!)]);
inputRef.current.value = ''; // limpa o FileList!

// ✅ Copiar primeiro
const files = Array.from(e.target.files ?? []);
if (files.length > 0) setFiles(prev => [...prev, ...files]);
inputRef.current.value = '';
```

## Renderização de Conteúdo

### ReactMarkdown + HTML raw
`react-markdown` NÃO renderiza HTML por padrão. Para tags como `<details>`, `<summary>`, etc:
- Instalar `rehype-raw`
- Adicionar `rehypePlugins={[rehypeRaw]}` em todo ReactMarkdown

### Dark mode com Tailwind prose
Classes prose com cores hardcoded `[#hex]` NÃO respondem ao `dark:prose-invert`. Usar classes Tailwind semânticas:
```
// ❌ Não funciona com dark mode
prose-p:text-[#475569] prose-th:bg-[#F1F5F9]

// ✅ Funciona com dark:prose-invert
prose-th:bg-slate-100 dark:prose-th:bg-slate-800
```

### ASCII art em markdown
Caracteres box-drawing (┌─┐│└┘) fora de code blocks quebram no markdown. Solução: pré-processar o markdown detectando linhas com box chars e envolvendo em code fences automaticamente. Melhor ainda: usar Mermaid.

### Mermaid.js para diagramas
- Renderiza diagramas como SVG bonito (fluxogramas, mindmaps, etc)
- Integrar via componente custom no ReactMarkdown que intercepta code blocks `language-mermaid`
- Customizar tema com `themeVariables` para cores da paleta do projeto
- Detectar dark mode e alternar tema: `theme: isDark ? 'dark' : 'default'`

## UX de Conteúdo Educativo

### Evitar repetição em conteúdo multi-fonte
Quando processar múltiplas fontes (aulas, slides), manter lista acumulativa de tópicos já abordados e passar como contexto negativo no prompt: "NÃO repita esses tópicos, foque no conteúdo novo".

### Prompts para IA educativa
- Pedir formato de SLIDES (seções curtas, max 400 palavras) em vez de textão
- Pedir Mermaid em vez de ASCII art
- Quizzes: NUNCA referenciar "aula", "professor", "vídeo" — o aluno estuda pelo material gerado
- Sempre pedir conteúdo no idioma do usuário independente do idioma da fonte

### Navegação em conteúdo longo
- Cards minimizados com expand para modo foco > rolagem infinita
- Slides com navegação anterior/próximo > accordion
- Auto-marcar como lido ao navegar
- Salvar progresso no localStorage por subject
- Barra de progresso visual (barrinhas coloridas por seção)

## Processo de Desenvolvimento (orquestração Forge)

### Briefing para o dev (subagente)
- Sempre incluir: arquivo, comportamento atual vs esperado, restrições
- Contexto ruim = código ruim. Investir tempo no briefing que o Forge passa ao subagente dev.

### Tester focado (subagente)
- Testar APENAS o que é relevante para o bug/feature
- NÃO rodar testes pré-existentes sem relação
- NÃO fazer verificações estáticas que o Forge já fez
- Ir direto ao teste funcional/E2E

### Cuidados com backend em produção
- Antes de mexer no backend, verificar se há processamento em andamento
- `tsx watch` recarrega rotas mas não interrompe Promises async em execução
- Migrations de banco são seguras (ALTER TABLE é atômico no SQLite)
