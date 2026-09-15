---
description: Prepara o repositório atual para rodar o Forge — grava as permissions (allow/ask/deny) em .claude/settings.json e os invariantes no CLAUDE.md
---

Você é o **Forge**. Este comando prepara o repositório **onde o usuário está agora** (não
necessariamente o repo de referência do Forge) para rodar o plugin. Sem isso, cada comando do
loop pede permissão a cada passo e — mais grave — falta a rede de segurança que impede deploy
acidental por iniciativa própria de um agente.

Carregue a skill `setup` antes de qualquer diagnóstico ou escrita — ela traz os dois blocos
canônicos (permissions e invariantes) e o algoritmo de merge. Siga esta ordem:

## 1. Diagnosticar antes de escrever

Rode o diagnóstico da skill `setup` e mostre o resultado ao usuário como uma lista curta
(✅ já está certo / ❌ falta):

- `.claude/settings.json` existe no repo atual? As entradas de `allow`/`ask`/`deny` do bloco
  canônico já estão lá? O que falta?
- `CLAUDE.md` (raiz do repo) existe e já tem o bloco entre `<!-- forge:inicio -->` e
  `<!-- forge:fim -->`? Está desatualizado em relação ao bloco canônico atual?
- `rtk` está no `PATH` (`which rtk`)? Informativo — **opcional**, a ausência não bloqueia
  nada.
- Detecte o modo: **fábrica** (raiz tem `projects/` **e** `templates/prompt.template.md`) ou
  **repo atual** (projeto avulso). Se for **fábrica**, avise que o repo já é a própria
  ferramenta do Forge e que é bem provável que permissions e `CLAUDE.md` já estejam certos —
  rode o diagnóstico do mesmo jeito e só proponha escrita se algo realmente faltar.

Se o diagnóstico já mostrar tudo ✅, diga isso ao usuário e pule direto para o passo 4 — não
proponha reescrever o que já está correto.

## 2. Mostrar o que vai mudar e confirmar

**Nunca sobrescreva `.claude/settings.json` ou `CLAUDE.md` existentes em silêncio.** Monte o
merge (skill `setup`) e mostre ao usuário só o **diff** — o que será adicionado, não o
arquivo inteiro:

- Em `settings.json`: as entradas novas de `allow`/`ask`/`deny`. Deixe explícito que o
  **`deny` é a parte mais importante** deste bloco: é o que impede `cdk deploy`,
  `terraform apply`, `docker push`, `kubectl apply` etc. por conta própria do agente — sem
  ele, a única barreira contra deploy acidental desaparece.
- Em `CLAUDE.md`: o bloco de invariantes que será inserido (arquivo novo ou sem marcadores)
  ou atualizado (marcadores já existentes).

Pergunte "Posso gravar?" e só escreva depois da confirmação explícita do usuário.

## 3. Escrever

- Grave `.claude/settings.json` (crie `.claude/` se não existir) aplicando o merge
  confirmado — sem remover nada que já estava lá.
- Grave/atualize o bloco entre `<!-- forge:inicio -->` e `<!-- forge:fim -->` no `CLAUDE.md`
  da raiz do repo (crie o arquivo se não existir). Rodar o comando de novo deve **atualizar**
  esse bloco no lugar, nunca duplicá-lo.

## 4. Fechar

Resuma o que foi gravado (ou confirme que já estava tudo certo) e feche dizendo: rode
`/forge` para começar.
