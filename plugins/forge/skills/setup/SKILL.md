---
name: setup
description: Use no comando /forge-setup — traz o bloco canônico de permissions (allow/ask/deny) para .claude/settings.json, o bloco canônico de invariantes para o CLAUDE.md, e o algoritmo de merge que preserva o que já existe no repo. Não sobrescreve nada sozinho.
---

# Setup do Forge num repositório

Dois artefatos não viajam dentro de um plugin e precisam ser gravados **no repositório onde
a pessoa vai trabalhar**: as `permissions` (allowlist de comandos + a rede de segurança que
bloqueia deploy) e o bloco de invariantes do `CLAUDE.md` (reenviado a cada turno, já que um
plugin não injeta `CLAUDE.md`). Esta skill traz os dois blocos canônicos — extraídos do
próprio repo de referência do Forge — e como mesclá-los sem apagar nada que o usuário já
tenha.

## Bloco canônico de permissions

Fonte: `.claude/settings.json` do repo de referência do Forge (41 `allow` / 6 `ask` / 8
`deny`). O **`deny`** é a parte mais importante do bloco — é o que impede `cdk deploy`,
`terraform apply`, `docker push`, `kubectl apply` etc. por iniciativa própria do agente. O
`ask` cobre operações destrutivas ou de rede que exigem confirmação explícita (`git push`,
`rm -r` e variantes, `killall`). O `allow` libera leitura, git de baixo risco, gerenciadores
de pacote e as variantes `rtk` (opcional — só fazem sentido se `rtk` estiver no `PATH`).

```json
{
  "permissions": {
    "defaultMode": "default",
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "WebSearch",
      "WebFetch",
      "Task",
      "Bash(pnpm:*)",
      "Bash(npm:*)",
      "Bash(npx:*)",
      "Bash(node:*)",
      "Bash(git init)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git status)",
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git log:*)",
      "Bash(git pull:*)",
      "Bash(git checkout:*)",
      "Bash(git branch:*)",
      "Bash(ls:*)",
      "Bash(mkdir:*)",
      "Bash(cat:*)",
      "Bash(find:*)",
      "Bash(rtk git status:*)",
      "Bash(rtk git diff:*)",
      "Bash(rtk git show:*)",
      "Bash(rtk git branch:*)",
      "Bash(rtk find:*)",
      "Bash(rtk ls:*)",
      "Bash(rtk tree:*)",
      "Bash(rtk jest:*)",
      "Bash(rtk vitest:*)",
      "Bash(rtk pytest:*)",
      "Bash(rtk playwright:*)",
      "Bash(rtk tsc:*)",
      "Bash(rtk ruff:*)",
      "Bash(rtk eslint:*)",
      "Bash(rtk lint:*)",
      "Bash(uv run rtk:*)",
      "Bash(pnpm exec rtk:*)"
    ],
    "ask": [
      "Bash(git push:*)",
      "Bash(killall:*)",
      "Bash(rm -r:*)",
      "Bash(rm -R:*)",
      "Bash(rm -fr:*)",
      "Bash(rm -fR:*)"
    ],
    "deny": [
      "Bash(cdk deploy:*)",
      "Bash(cdk destroy:*)",
      "Bash(terraform apply:*)",
      "Bash(terraform destroy:*)",
      "Bash(serverless deploy:*)",
      "Bash(sam deploy:*)",
      "Bash(docker push:*)",
      "Bash(kubectl apply:*)"
    ]
  }
}
```

### Algoritmo de merge para `.claude/settings.json`

1. Se o arquivo **não existir**: crie `.claude/` e o arquivo com exatamente o objeto acima
   (só a chave `permissions`). Não invente `hooks` nem `model` — isso é do plugin, não do
   setup.
2. Se o arquivo **existir**:
   - Faça `json.load` do arquivo. Se der erro de parse, pare e avise o usuário — não
     sobrescreva um JSON quebrado às cegas.
   - Se não existir a chave `permissions`, crie-a com `{"defaultMode": "default", "allow": [],
     "ask": [], "deny": []}` antes de mesclar.
   - Para cada uma de `allow`, `ask`, `deny`: una a lista existente com a canônica,
     **preservando a ordem do que já está lá** e **anexando ao final** só as entradas
     canônicas que ainda não existem (comparação por string exata). Nunca remova uma entrada
     que já estava no arquivo, mesmo que não pareça relacionada ao Forge.
   - Não toque em nenhuma outra chave do arquivo (`defaultMode` se já setado, `hooks`,
     `model`, outras chaves de `permissions` como `additionalDirectories`, etc.).
3. Antes de gravar, mostre ao usuário só o **diff** (as entradas novas por lista) — nunca o
   arquivo inteiro como se fosse tudo novo.

## Bloco canônico de invariantes (para `CLAUDE.md`)

Destilado dos 6 invariantes do `CLAUDE.md` do repo de referência do Forge — curto de
propósito, porque é reenviado a cada turno. O detalhe de cada um vive nas skills do plugin
(citado no próprio bloco).

```markdown
<!-- forge:inicio -->
## Forge — invariantes (reenviados a cada turno; detalhe nas skills do plugin `forge`)

1. **Não escreva código de produto** — delegue ao subagente `dev`; um hook bloqueia por
   caminho.
2. **Nunca `push` ou deploy por conta própria** (`git push`, `cdk deploy/destroy`,
   `terraform apply/destroy`, `serverless deploy`, `sam deploy`, `docker push`,
   `kubectl apply`) — só sob ordem explícita do usuário. Skill `no-deploy-no-push`.
3. **Commits em português do Brasil** (prefixos convencionais em inglês são ok: `feat:`,
   `fix:`...).
4. **Segurança de processos e do sistema**: confira processos ativos antes de matar/reiniciar;
   pesquise tecnologia nova incluindo o ano atual na busca; pergunte o perfil git se o usuário
   não especificou. Skills `safe-operations`, `search-before-code`, `git-profiles`.
5. **Paralelize por padrão**: antes de invocar qualquer subagente, pergunte "o que mais pode
   rodar junto?" e dispare tudo na mesma mensagem — chamadas separadas viram fila.
6. **Cada token reenviado é pago de novo**: decomponha tarefas para caber em poucos turnos de
   subagente, nomeie 1–2 skills por briefing, prefira `Grep`/`Glob`/`Read` a `grep`/`find`/
   `cat`. Skill `orchestrator`.
<!-- forge:fim -->
```

### Algoritmo de merge para `CLAUDE.md`

1. Se o arquivo **não existir**: crie-o só com o bloco acima (com os marcadores).
2. Se o arquivo **existir** e já tiver `<!-- forge:inicio -->` ... `<!-- forge:fim -->`:
   substitua **apenas o conteúdo entre os marcadores** (marcadores inclusos) pelo bloco
   canônico. Isso é o que torna rodar `/forge-setup` de novo uma atualização, não uma
   duplicação. O resto do `CLAUDE.md` (regras do usuário, de outro projeto, etc.) fica
   intocado.
3. Se o arquivo **existir** e **não tiver** os marcadores: anexe o bloco ao final, separado
   por uma linha em branco. Não reescreva nada que já estava no arquivo.
4. Se houver **mais de um par** de marcadores (arquivo malformado por edição manual), pare e
   avise o usuário em vez de adivinhar qual par é o correto.

## Diagnóstico (antes de escrever)

- `.claude/settings.json` existe? As entradas do bloco canônico já estão todas lá (allow/ask/
  deny)? Liste o que falta.
- `CLAUDE.md` (raiz do repo) existe? Já tem os marcadores `forge:inicio`/`forge:fim`? O
  conteúdo entre eles bate com o bloco canônico atual?
- `rtk` está no `PATH` (`which rtk`)? Informativo — a ausência não bloqueia nada; as entradas
  `Bash(rtk ...)` do `allow` simplesmente não terão efeito sem o binário.
- Modo do repo: **fábrica** se a raiz tiver `projects/` **e** `templates/prompt.template.md`;
  caso contrário, **repo atual** (um projeto avulso rodando o Forge nele). No modo fábrica,
  avise que o repo já é a própria ferramenta e que é bem provável que as permissions e o
  `CLAUDE.md` já estejam corretos — rode o diagnóstico do mesmo jeito e só escreva se algo
  faltar de fato.
