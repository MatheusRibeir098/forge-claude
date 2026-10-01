---
name: setup-blocos
description: Use no comando /forge:setup — traz o bloco canônico de permissions (allow/ask/deny) para .claude/settings.json, o bloco canônico de invariantes para o CLAUDE.md, o modelo canônico da skill de usuário credenciais-ambiente (mapa local de credenciais da máquina, só ponteiros, sem segredos), o algoritmo de merge que preserva o que já existe no repo ou na máquina, a receita para criar a fábrica de projetos do zero e o passo a passo para oferecer a instalação do rtk. Não sobrescreve nada sozinho.
---

> ⚠️ **Escreva com `Write`/`Edit`, nunca por `Bash`.** O hook do Forge libera, na raiz do
> projeto, exatamente os arquivos que este comando precisa criar (`.claude/settings.json`,
> `.gitignore`, `projects/.gitkeep`, `CLAUDE.md`). Se algum for barrado, isso é um bug do
> hook — **reporte, não contorne por `Bash`**: escrever por fora fura o invariante por um
> caminho que o hook não vê, e ninguém fica sabendo.

# Setup do Forge num repositório

Dois artefatos não viajam dentro de um plugin e precisam ser gravados **no repositório onde
a pessoa vai trabalhar**: as `permissions` (allowlist de comandos + confirmação nas
operações destrutivas) e o bloco de invariantes do `CLAUDE.md` (reenviado a cada turno, já que um
plugin não injeta `CLAUDE.md`). Esta skill traz os dois blocos canônicos — extraídos do
próprio repo de referência do Forge — e como mesclá-los sem apagar nada que o usuário já
tenha.

## Bloco canônico de permissions

Fonte: `.claude/settings.json` do repo de referência do Forge (41 `allow` / 6 `ask` /
3 `deny`). O `ask` cobre operações destrutivas ou de rede que exigem confirmação
explícita (`git push`, `rm -r` e variantes, `killall`). O `allow` libera leitura, git de
baixo risco, gerenciadores de pacote e as variantes `rtk` (opcional — só fazem sentido se
`rtk` estiver no `PATH`). O `deny` traz só o mínimo genérico: `git push` forçado (`--force`, `-f`,
`--force-with-lease`). A regra de **não fazer deploy nem `push` por conta própria** vive no
invariante 2 do `CLAUDE.md` (skill `no-deploy-no-push`), não numa lista de comandos de um
provedor específico. Quem quiser bloquear comandos próprios do seu stack adiciona as regras
em `deny` — o algoritmo de merge
abaixo nunca remove o que já está lá.

**Por que `ask` e não `allow` no que é destrutivo**: `git push` e `rm -r` não têm volta
fácil; a ferramenta precisa parar e pedir confirmação em vez de executar sozinha.

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
      "Bash(git push --force*)",
      "Bash(git push -f*)",
      "Bash(git push --force-with-lease*)"
    ]
  }
}
```

O `Bash(...)` só casa **prefixo exato + `:*`** — não existe glob no meio do comando. Por isso
as regras são rede de segurança, não a única camada: flags ou encadeamentos antes do comando
mudam o começo da string e escapam do prefixo. O que cobre o resto é o comportamento descrito
nas skills do plugin (`no-deploy-no-push`, `safe-operations`) e os hooks.

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
2. **Nunca `git push` nem deploy de qualquer tipo** (infra, container, serverless, cloud)
   por conta própria — só sob ordem explícita do usuário; antes de aplicar infra, mostre o
   diff/plano e aguarde. Skill `no-deploy-no-push`.
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

### Invariantes extras — só quando a raiz for uma **fábrica**

Se o diagnóstico detectou modo fábrica (a raiz tem `projects/` e
`templates/prompt.template.md`), acrescente **os itens 7 e 8** abaixo ao bloco, antes do
`<!-- forge:fim -->`.

O item 7 existe porque, sem ele, o `CLAUDE.md` não diz onde os projetos moram, e qualquer
pedido de clonar ou criar projeto cai na raiz ou no diretório pessoal — foi o que aconteceu
num teste real: o usuário pediu "clone o repositório X" estando na fábrica, e o clone foi
parar em `~/`.

O item 8 existe porque, num outro teste real, o orquestrador conseguiu escrever código de
produto depois que a sessão passou a operar dentro de `projects/<nome>/` — um repositório
git separado, sem este `CLAUDE.md` e (pelo que a documentação do Claude Code não deixa claro)
sem garantia de que os hooks do plugin disparem fora da raiz onde ele foi habilitado. Como
esse `CLAUDE.md` só é reenviado enquanto a sessão continuar na raiz da fábrica, o item 8 é a
segunda camada de defesa (a primeira é o hook) para o caso de a sessão mudar de diretório no
meio da conversa — não cobre uma sessão aberta direto dentro do projeto filho, por isso o
aviso equivalente também está no README, fora da sessão.

```markdown
7. **Esta pasta é a fábrica do Forge.** Todo projeto vive em `projects/<nome>/`, com git
   próprio — tanto o criado do zero quanto o clonado
   (`git clone <url> projects/<nome>`). Nunca clone nem crie projeto na raiz, no diretório
   pessoal, ou em qualquer lugar fora de `projects/`. O controle de cada projeto fica em
   `projects/<nome>/.forge/`. Isso vale mesmo sem ter rodado `/forge:forge`.
8. **Nunca opere de dentro de `projects/<nome>/`.** Esse diretório é um repositório git
   separado, sem este `CLAUDE.md` e sem garantia de que os hooks do plugin disparem ali. Se
   a sessão mudar de diretório para dentro de um projeto (por `cd` ou por ter sido aberta lá),
   pare e diga ao usuário para reabrir na raiz da fábrica antes de continuar — não trate a
   ausência de bloqueio como permissão.
```

Os itens 7 e 8 são os únicos que dependem do modo. Em modo repo atual, o bloco termina no
item 6.

<!-- forge:fim -->
```

### Algoritmo de merge para `CLAUDE.md`

1. Se o arquivo **não existir**: crie-o só com o bloco acima (com os marcadores).
2. Se o arquivo **existir** e já tiver `<!-- forge:inicio -->` ... `<!-- forge:fim -->`:
   substitua **apenas o conteúdo entre os marcadores** (marcadores inclusos) pelo bloco
   canônico. Isso é o que torna rodar `/forge:setup` de novo uma atualização, não uma
   duplicação. O resto do `CLAUDE.md` (regras do usuário, de outro projeto, etc.) fica
   intocado.
3. Se o arquivo **existir** e **não tiver** os marcadores: anexe o bloco ao final, separado
   por uma linha em branco. Não reescreva nada que já estava no arquivo.
4. Se houver **mais de um par** de marcadores (arquivo malformado por edição manual), pare e
   avise o usuário em vez de adivinhar qual par é o correto.

## Modelo canônico da skill `credenciais-ambiente`

O **mapa de credenciais** — quais perfis de nuvem, contas e tokens existem nesta máquina,
para que serve cada um e qual é produção — é diferente em cada máquina e **não pode** ir
dentro do plugin: distribuir o mapa de uma pessoa para outras seria pior que inútil, seria
enganoso. Por isso ele é **opcional** e é gravado como skill do **usuário**, em
`~/.claude/skills/credenciais-ambiente/SKILL.md` — fora do repositório, valendo em qualquer
projeto que essa pessoa abrir.

É um mapa de **ponteiros**, não um cofre: diz *onde* a credencial vive e *como* confirmar que
está ativa, nunca o valor dela. Não assuma provedor nenhum — o usuário diz o que quer mapear.

### Perguntar antes de tudo

Pergunte se o usuário quer criar esse mapa. Se disser **não**, pule — nada é criado e o setup
segue. Se disser **sim**, pergunte **o que ele quer mapear**. Exemplos para destravar a
resposta (não são lista fechada): perfis de nuvem (AWS, GCP, Azure…), contas do `gh`, tokens
de API (ClickUp, Notion…), service accounts, bancos de dados.

### Inferir o que der, sem tocar em segredo

Para cada tipo que o usuário pediu, use só fontes que **não contêm o segredo em si**:

- contas do GitHub: `gh auth status`;
- perfis AWS: nomes e metadados de `~/.aws/config` (se existir) — nome do profile, `region`,
  `sso_*`, `role_arn`, `source_profile`;
- perfis GCP: `gcloud config configurations list`;
- perfis Azure: `az account list --query "[].{name:name,id:id}"`;
- outros: nada a inferir — pergunte.

Rodar um comando de listagem acima só é ok se a ferramenta existir; se não existir, não é
erro, vira pergunta ao usuário.

### Perguntar o que não dá para inferir

Para cada item, numa rodada objetiva:

1. Para que serve?
2. Onde a credencial vive? (variável de ambiente `X`, arquivo `Y`, keychain, `gh auth`…)
3. Como renovar a sessão e como confirmar que está ativa?
4. É **produção**? Tem acesso **administrativo**? É de **cliente/terceiro**?
5. Algum item **não deve ser usado por agente nenhum**?

Não adivinhe produção/admin por nome — `prd`, `prod`, `admin` no nome são pista, não
confirmação.

### Template do arquivo gerado

Gere só as seções dos tipos que o usuário mapeou; omita as vazias.

````markdown
---
name: credenciais-ambiente
description: Mapa local das credenciais e perfis desta máquina — contas de nuvem, GitHub, tokens de API, service accounts e bancos: para que serve cada um, onde a credencial vive, como confirmar que está ativa e qual é produção. Use antes de escolher um perfil/conta/token, ou ao diagnosticar erro de credencial (expired token, access denied, "session expired", "unauthorized", "unable to locate credentials"). Não contém segredos — aponta para onde eles vivem.
---

# Credenciais e perfis desta máquina

Mapa de **qual credencial usar para quê** — isto é um mapa, não um cofre: nenhum segredo
(chave, token, senha, JSON de service account) é gravado aqui.

## Perfis de nuvem

| Perfil | Provedor | Para que serve | Onde a credencial vive | Como confirmar | Risco |
|---|---|---|---|---|---|
| `<nome>` | <provedor> | <descrição dada pelo usuário> | <env var / arquivo / SSO / keychain> | `<comando de identidade>` | — / **PRODUÇÃO** / **ADMIN** / cliente terceiro / **não usar** |

## Contas do GitHub (`gh`)

| Conta | Para que serve | Como confirmar | Risco |
|---|---|---|---|
| `<usuário>` | <descrição> | `gh auth status` | — |

## Tokens de API

| Serviço | Para que serve | Onde o token vive | Como renovar / confirmar | Risco |
|---|---|---|---|---|
| `<serviço>` | <descrição> | variável de ambiente `<NOME>` | <como> | — |

## Service accounts e bancos

| Item | Para que serve | Onde a credencial vive | Como confirmar | Risco |
|---|---|---|---|---|
| `<nome>` | <descrição> | arquivo `<caminho>` / variável `<NOME>` | <como> | — |

## Sem segredos aqui

Este arquivo não contém chaves de acesso, tokens, senhas nem conteúdo de service account. As
credenciais de verdade vivem onde a coluna "onde a credencial vive" aponta — nunca neste
arquivo. Os comandos de confirmação de identidade são a fonte de verdade: este mapa diz o que
**deveria** ser, eles dizem o que **é**.
````

Uma linha por item mapeado, cruzando com as respostas do usuário na coluna "Risco". Um item
marcado como "não deve ser usado por agente nenhum" entra na tabela do mesmo jeito, com essa
observação na coluna Risco — omitir o item é pior do que marcá-lo como proibido, porque um
item ausente parece apenas "ainda não catalogado".

### Algoritmo de merge (não sobrescrever)

1. Se `~/.claude/skills/credenciais-ambiente/SKILL.md` **não existir**: gere o arquivo
   completo a partir do template acima.
2. Se **já existir**: **nunca sobrescreva**. Diga ao usuário que o arquivo já existe e
   ofereça só **complementar**:
   - Leia as tabelas existentes e extraia os nomes já catalogados.
   - Compare com o que foi inferido ou o usuário pediu para mapear agora.
   - Pergunte (mesma rodada de perguntas acima) só sobre os itens que **faltam**.
   - Acrescente uma linha por item novo na tabela do tipo certo (crie a seção se o tipo
     ainda não existir), preservando todas as linhas e anotações que já estavam lá. Nunca
     remova ou reescreva uma linha existente.
   - Se nenhum item novo for encontrado, diga isso ao usuário e não escreva nada.

### Proibições absolutas

- **Nunca leia arquivos que contêm o segredo em si**: `~/.aws/credentials`, `.env` com
  tokens, JSON de service account, arquivos de chave (`*.pem`, `id_*`), cofres de senha. Para
  AWS, só `~/.aws/config`.
- **Nunca grave** chave de acesso, token, senha, session token ou qualquer segredo na skill
  gerada.
- Se o usuário colar uma credencial na conversa (por engano ou "para facilitar"), **não
  grave**: diga que ela não vai para arquivo nenhum e siga sem ela.

## Diagnóstico (antes de escrever)

- `.claude/settings.json` existe? As entradas do bloco canônico já estão todas lá (allow/ask/
  deny)? Liste o que falta.
- `CLAUDE.md` (raiz do repo) existe? Já tem os marcadores `forge:inicio`/`forge:fim`? O
  conteúdo entre eles bate com o bloco canônico atual?
- `rtk` está instalado? Detecte com `FORGE_RTK_BIN` (se a variável estiver definida, é esse o
  binário) senão `command -v rtk`. Informativo para o merge de permissions — a ausência não
  bloqueia nada; as entradas `Bash(rtk ...)` do `allow` simplesmente não terão efeito sem o
  binário. Mas alimenta a oferta de instalação (seção "Instalar o rtk" abaixo).
- Modo do repo: **fábrica** se a raiz tiver `projects/` **e** `templates/prompt.template.md`;
  caso contrário, **repo atual** (um projeto avulso rodando o Forge nele). No modo fábrica,
  avise que o repo já é a própria ferramenta e que é bem provável que as permissions e o
  `CLAUDE.md` já estejam corretos — rode o diagnóstico do mesmo jeito e só escreva se algo
  faltar de fato. No modo repo atual, é essa a deixa para oferecer criar a fábrica (seção
  "Criar a fábrica" abaixo) — quem só tem um repo avulso pode não saber que a opção existe.

## Criar a fábrica

O modo fábrica (definido no hook `deny-orchestrator-code-edits.sh`, que decide por onde o
orquestrador pode escrever) pressupõe uma pasta base já existente: raiz com `projects/` **e**
`templates/prompt.template.md`. Esta seção é a receita para criar essa base do zero, quando o
usuário quer começar projetos novos em vez de só preparar o repositório onde já está.

O fluxo de referência (do autor da ferramenta) é: uma única pasta base, cada repositório em
que ele trabalha clonado para dentro dela (`projects/app-web`, `projects/api-pagamentos`, …), e um
único orquestrador rodando sempre na raiz da base — que sabe onde cada projeto está. Projeto
novo nasce em `projects/<nome>/`, cada um com o **próprio git**; a base em si nunca é
repositório e nunca versiona `projects/`.

**Pré-requisito**: confirme o caminho da base com o usuário antes de criar qualquer coisa.
Sugira `~/forge`, mas não presuma — pode já existir uma pasta parecida. Se o caminho já
existir e tiver conteúdo, mostre o que há e confirme que pode prosseguir.

Estrutura a criar em `<base>/`:

1. `projects/` com um `.gitkeep` dentro (vazio, só para a pasta existir e ser versionável pelo
   `.gitignore` abaixo mesmo sem projetos ainda).
2. `templates/`, copiando os arquivos **de dentro do plugin** — nunca suponha um `templates/`
   relativo ao diretório atual; o caminho canônico é `${CLAUDE_PLUGIN_ROOT}/templates/`, que
   hoje contém `prompt.template.md` e `.npmrc`. Copie os dois.
3. `CLAUDE.md` com o bloco canônico de invariantes (o mesmo bloco desta skill, seção acima) —
   mesmo algoritmo de merge: se o arquivo já existir com os marcadores, atualiza o conteúdo
   entre eles; sem marcadores, anexa; sem arquivo, cria.
4. `.claude/settings.json` com o bloco canônico de permissions (mesma seção acima, mesmo
   algoritmo de merge).
5. `.gitignore` com:
   ```
   projects/*
   !projects/.gitkeep
   ```
   Isso é o que garante que a base não versiona os projetos clonados dentro dela — cada um
   tem o próprio repositório.

**Não rode `git init`** na base. Ela é diretório de trabalho, não repositório — o git de
verdade vive em cada `projects/<nome>/`.

Se o diagnóstico já mostrar fábrica (raiz com `projects/` e `templates/prompt.template.md`),
diga isso ao usuário e não crie nada.

## Instalar o rtk

O `rtk` ("Rust Token Killer") é um proxy de CLI que comprime a saída de comandos antes dela
entrar no contexto. Os hooks do plugin (`rtk-root.sh`, `subagent-turn-budget.sh` e as entradas
`Bash(rtk ...)` do bloco de permissions) já o encadeiam quando ele existe, e **degradam em
silêncio** quando não existe — isso é deliberado e deve continuar assim; a ausência do rtk
nunca pode quebrar nada.

**Detecção**: `FORGE_RTK_BIN` se definida, senão `command -v rtk`.

**Se não existir, oferecer a instalação** — nunca instalar sem confirmação explícita do
usuário, porque é download e execução de script remoto. Mostre o comando, explique o que ele
faz, pergunte, e só rode depois do "sim":

```bash
curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
```

Esse é o **único** comando verificado como funcional; ele instala o binário em
`~/.local/bin/rtk`.

⚠️ **Nunca** use `https://rtk-ai.app/install.sh` — devolve HTTP 404 com uma página HTML, e um
`curl | sh` nesse endereço executaria a página de erro em vez do instalador. Testado em
set/2026.

Se o usuário recusar, siga normalmente e diga que o Forge funciona sem o rtk — é só uma
otimização, não um requisito. Depois de instalar (se aceito), avise que `~/.local/bin`
precisa estar no `PATH` e que dá para conferir com `rtk --version`.

**Seja honesto sobre o ganho — com o número medido, não com o anunciado pela ferramenta.** No
perfil de comandos do repositório de origem do Forge: o rtk cortou **~4,5% do volume total de
Bash** — bem abaixo dos "60–90%" que a ferramenta anuncia. Por comando: `git status` 76%,
`tree` 98%, `find` 51%, build 17%; `cat`/`sed`/`grep` deram 0% (nada a comprimir nesses
casos). O ganho maior de token não vem do rtk — vem das regras de briefing dos agentes (usar
`Grep`/`Glob`/`Read` em vez de `grep`/`find`/`cat`, ver invariante 6 do `CLAUDE.md` da
fábrica). Quem instala o rtk tem que saber que o ganho real é modesto e localizado, não a
promessa de 60–90%.
