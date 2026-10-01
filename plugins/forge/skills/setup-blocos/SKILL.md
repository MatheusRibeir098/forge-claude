---
name: setup-blocos
description: Use no comando /forge:setup — traz o bloco canônico de permissions (allow/ask/deny) para .claude/settings.json, o bloco canônico de invariantes para o CLAUDE.md, o modelo canônico da skill de usuário credenciais-ambiente (mapa de profiles AWS, sem segredos), o algoritmo de merge que preserva o que já existe no repo ou na máquina, a receita para criar a fábrica de projetos do zero e o passo a passo para oferecer a instalação do rtk. Não sobrescreve nada sozinho.
---

> ⚠️ **Escreva com `Write`/`Edit`, nunca por `Bash`.** O hook do Forge libera, na raiz do
> projeto, exatamente os arquivos que este comando precisa criar (`.claude/settings.json`,
> `.gitignore`, `projects/.gitkeep`, `CLAUDE.md`). Se algum for barrado, isso é um bug do
> hook — **reporte, não contorne por `Bash`**: escrever por fora fura o invariante por um
> caminho que o hook não vê, e ninguém fica sabendo.

# Setup do Forge num repositório

Dois artefatos não viajam dentro de um plugin e precisam ser gravados **no repositório onde
a pessoa vai trabalhar**: as `permissions` (allowlist de comandos + a rede de segurança que
bloqueia deploy) e o bloco de invariantes do `CLAUDE.md` (reenviado a cada turno, já que um
plugin não injeta `CLAUDE.md`). Esta skill traz os dois blocos canônicos — extraídos do
próprio repo de referência do Forge — e como mesclá-los sem apagar nada que o usuário já
tenha.

## Bloco canônico de permissions

Fonte: `.claude/settings.json` do repo de referência do Forge (41 `allow` / 31 `ask` / 70
`deny`). O **`deny`** é a parte mais importante do bloco — é o que impede `cdk deploy`,
`terraform apply`, `docker push`, `kubectl apply` etc. por iniciativa própria do agente, e
agora também o `aws` CLI cru nas ações irreversíveis ou de blast radius alto (`aws s3 rm`,
`delete-*` de banco/stack/função/cluster, `terminate-instances`, e qualquer mudança de
identidade via `aws iam`/`aws organizations`). O `ask` cobre operações destrutivas ou de
rede que exigem confirmação explícita (`git push`, `rm -r` e variantes, `killall`) e agora
também as mutações reversíveis do `aws` CLI (`create-*`/`update-*`/`put-*`/`modify-*` em
serviços de dado e compute, e o `create-stack`/`update-stack` do CloudFormation, que senão
contornaria o gate do `cdk deploy`/`terraform apply`). O `allow` libera leitura, git de
baixo risco, gerenciadores de pacote e as variantes `rtk` (opcional — só fazem sentido se
`rtk` estiver no `PATH`); não foi alterado — leitura de `aws` CLI (`describe-*`, `list-*`,
`get-*`) já passava livre e continua passando.

**Por que `deny` e não só `ask` no que é irreversível**: `ask` depende de alguém ler o
prompt de confirmação e dizer não — um só "sim" apressado (ou um agente que interpreta
contexto ambíguo como autorização) já executa. Para o que não tem volta (deletar um bucket,
terminar uma instância, apagar uma stack), a ferramenta não deve nem oferecer a opção; por
isso vai para `deny`, que bloqueia sem perguntar.

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
      "Bash(rm -fR:*)",
      "Bash(aws s3api create-bucket:*)",
      "Bash(aws s3api put-bucket-policy:*)",
      "Bash(aws s3api put-bucket-acl:*)",
      "Bash(aws rds create-db-instance:*)",
      "Bash(aws rds create-db-cluster:*)",
      "Bash(aws rds modify-db-instance:*)",
      "Bash(aws rds modify-db-cluster:*)",
      "Bash(aws dynamodb create-table:*)",
      "Bash(aws dynamodb update-table:*)",
      "Bash(aws cloudformation create-stack:*)",
      "Bash(aws cloudformation update-stack:*)",
      "Bash(aws cloudformation create-change-set:*)",
      "Bash(aws cloudformation execute-change-set:*)",
      "Bash(aws lambda create-function:*)",
      "Bash(aws lambda update-function-code:*)",
      "Bash(aws lambda update-function-configuration:*)",
      "Bash(aws ecs create-cluster:*)",
      "Bash(aws ecs create-service:*)",
      "Bash(aws ecs update-service:*)",
      "Bash(aws eks create-cluster:*)",
      "Bash(aws eks create-nodegroup:*)",
      "Bash(aws eks update-nodegroup-config:*)",
      "Bash(aws ec2 run-instances:*)",
      "Bash(aws ec2 create-vpc:*)",
      "Bash(aws ec2 stop-instances:*)"
    ],
    "deny": [
      "Bash(cdk deploy:*)",
      "Bash(cdk destroy:*)",
      "Bash(terraform apply:*)",
      "Bash(terraform destroy:*)",
      "Bash(serverless deploy:*)",
      "Bash(sam deploy:*)",
      "Bash(docker push:*)",
      "Bash(kubectl apply:*)",
      "Bash(aws s3 rm:*)",
      "Bash(aws s3 rb:*)",
      "Bash(aws s3api delete-bucket:*)",
      "Bash(aws s3api delete-object:*)",
      "Bash(aws s3api delete-objects:*)",
      "Bash(aws rds delete-db-instance:*)",
      "Bash(aws rds delete-db-cluster:*)",
      "Bash(aws rds delete-db-snapshot:*)",
      "Bash(aws rds delete-db-cluster-snapshot:*)",
      "Bash(aws dynamodb delete-table:*)",
      "Bash(aws dynamodb delete-backup:*)",
      "Bash(aws cloudformation delete-stack:*)",
      "Bash(aws cloudformation delete-stack-set:*)",
      "Bash(aws cloudformation delete-stack-instances:*)",
      "Bash(aws lambda delete-function:*)",
      "Bash(aws lambda delete-layer-version:*)",
      "Bash(aws ecs delete-cluster:*)",
      "Bash(aws ecs delete-service:*)",
      "Bash(aws eks delete-cluster:*)",
      "Bash(aws eks delete-nodegroup:*)",
      "Bash(aws ec2 terminate-instances:*)",
      "Bash(aws kms schedule-key-deletion:*)",
      "Bash(aws secretsmanager delete-secret:*)",
      "Bash(aws iam create-user:*)",
      "Bash(aws iam delete-user:*)",
      "Bash(aws iam create-role:*)",
      "Bash(aws iam delete-role:*)",
      "Bash(aws iam update-assume-role-policy:*)",
      "Bash(aws iam create-policy:*)",
      "Bash(aws iam delete-policy:*)",
      "Bash(aws iam create-policy-version:*)",
      "Bash(aws iam delete-policy-version:*)",
      "Bash(aws iam attach-role-policy:*)",
      "Bash(aws iam detach-role-policy:*)",
      "Bash(aws iam attach-user-policy:*)",
      "Bash(aws iam detach-user-policy:*)",
      "Bash(aws iam attach-group-policy:*)",
      "Bash(aws iam detach-group-policy:*)",
      "Bash(aws iam put-role-policy:*)",
      "Bash(aws iam put-user-policy:*)",
      "Bash(aws iam put-group-policy:*)",
      "Bash(aws iam create-access-key:*)",
      "Bash(aws iam delete-access-key:*)",
      "Bash(aws iam update-access-key:*)",
      "Bash(aws iam create-login-profile:*)",
      "Bash(aws iam delete-login-profile:*)",
      "Bash(aws iam update-login-profile:*)",
      "Bash(aws iam add-user-to-group:*)",
      "Bash(aws iam remove-user-from-group:*)",
      "Bash(aws iam deactivate-mfa-device:*)",
      "Bash(aws iam delete-virtual-mfa-device:*)",
      "Bash(aws organizations create-account:*)",
      "Bash(aws organizations close-account:*)",
      "Bash(aws organizations remove-account-from-organization:*)",
      "Bash(aws organizations invite-account-to-organization:*)",
      "Bash(aws organizations leave-organization:*)",
      "Bash(aws organizations create-policy:*)",
      "Bash(aws organizations delete-policy:*)",
      "Bash(aws organizations update-policy:*)",
      "Bash(aws organizations attach-policy:*)",
      "Bash(aws organizations detach-policy:*)",
      "Bash(aws organizations move-account:*)"
    ]
  }
}
```

O `Bash(...)` só casa **prefixo exato + `:*`** — não existe glob no meio do comando. Por
isso as entradas de `aws iam`/`aws organizations` acima listam ação por ação (`create-role`,
`attach-role-policy`, ...) em vez de tentar um padrão único: cobrem as mutações mais comuns e
de maior blast radius, não literalmente toda ação da API. Isso é rede de segurança, não a
única camada — a skill `aws-operacoes-seguras` é quem cobre o resto (confirmar conta/perfil
antes de agir, nunca supor `default`, tratar qualquer comando fora do `allow` com o mesmo
cuidado mesmo que a lista não tenha previsto a ação exata).

**O prefixo literal tem um furo mensurável**: qualquer flag global do `aws` antes do serviço
(`aws --profile prod s3 rm ...`, `aws --region us-east-1 iam delete-role ...`) muda o começo
da string e escapa do `deny` — mesmo sendo exatamente a forma usada quando alguém aponta pra
produção. Quem fecha esse furo é o hook `PreToolUse` `deny-aws-destrutivo`: ele lê
`tool_input.command`, acha toda invocação do `aws` (direta, encadeada ou dentro de
`bash -c`), ignora as flags globais e decide pelo serviço + operação de verdade. A lista de
`permissions` continua valendo como primeira camada (mais rápida, cobre o resto do
ecossistema de infra); o hook é a segunda, específica para o `aws` CLI.

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

A skill `aws-operacoes-seguras` do plugin é regra de comportamento ("confirme a conta antes
de agir") e vale para qualquer instalação. Mas o **mapa de profiles AWS** — qual é produção,
qual é administrador — é diferente em cada máquina e **não pode** ir dentro do plugin:
distribuir o mapa de uma pessoa para o time seria pior que inútil, seria enganoso. Por isso
ele é gravado como skill do **usuário**, em `~/.claude/skills/credenciais-ambiente/SKILL.md`
— fora do repositório, valendo em qualquer projeto que essa pessoa abrir.

### Descobrir os profiles

Leia **somente** `~/.aws/config`. ⚠️ **Nunca leia `~/.aws/credentials`** — é lá que ficam as
chaves de verdade, e nada dele entra na skill gerada. De cada bloco `[profile <nome>]` (ou
`[default]`), aproveite só:

- nome do profile;
- `region`;
- `sso_start_url`, `sso_account_id`, `sso_role_name` (perfis SSO);
- `role_arn`, `source_profile` (assume-role);
- `output`.

Nenhum outro campo do `config` importa para o mapa.

### Perguntar o que não dá para inferir

Numa única rodada, objetiva:

1. Qual(is) profile(s) apontam para **produção**?
2. Qual(is) têm **acesso administrativo**?
3. Algum é de **cliente/terceiro**?
4. Existe algum que **não deve ser usado** por agente nenhum?

Não adivinhe essas respostas por nome de profile — `prd`, `prod`, `admin` no nome são pista,
não confirmação.

### Template do arquivo gerado

````markdown
---
name: credenciais-ambiente
description: Mapa dos profiles AWS configurados nesta máquina — para que serve cada um, região, tipo de autenticação e risco (produção/administrador). Use antes de escolher um profile AWS, ou ao diagnosticar erro de credencial (ExpiredToken, AccessDenied, "sso session expired", "Unable to locate credentials"). Não contém segredos — aponta para onde eles vivem.
---

# Profiles AWS desta máquina

Mapa de **qual profile usar para quê** — isto é um mapa, não um cofre: nenhum segredo
(access key, secret key, session token, senha, token de API) é gravado aqui.

## Profiles

| Profile | Para que serve | Região | Autenticação | Risco |
|---|---|---|---|---|
| `<nome>` | <descrição dada pelo usuário> | `<region>` | chave estática / SSO + assume-role | — / **PRODUÇÃO** / **ADMIN** / cliente terceiro |

## Renovar sessão e confirmar onde você está

```bash
aws sso login --profile <profile-sso>
aws sts get-caller-identity --profile <profile>
```

`sts get-caller-identity` continua sendo a fonte de verdade — este mapa diz o que
**deveria** ser, o `sts` diz o que **é**.

## Sem segredos aqui

Este arquivo não contém `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`,
senha nem token de API. As credenciais de verdade vivem em `~/.aws/config` (profiles e
metadados de SSO), `~/.aws/credentials` (chaves estáticas) e no cache de sessão do SSO —
nunca neste arquivo.
````

Preencha a tabela com uma linha por profile encontrado em `~/.aws/config`, cruzando com as
respostas do usuário para a coluna "Risco". Um profile marcado como "não deve ser usado por
agente nenhum" entra na tabela do mesmo jeito, com essa observação na coluna Risco — omitir
o profile é pior do que marcá-lo como proibido, porque um profile ausente parece apenas
"ainda não catalogado".

### Algoritmo de merge (não sobrescrever)

1. Se `~/.claude/skills/credenciais-ambiente/SKILL.md` **não existir**: gere o arquivo
   completo a partir do template acima.
2. Se **já existir**: **nunca sobrescreva**. Diga ao usuário que o arquivo já existe e
   ofereça só **complementar**:
   - Leia a tabela existente e extraia os nomes de profile já catalogados.
   - Compare com os profiles encontrados em `~/.aws/config`.
   - Pergunte ao usuário (mesma rodada de perguntas acima) só sobre os profiles que
     **faltam** na tabela.
   - Acrescente uma linha por profile novo à tabela existente, preservando todas as linhas
     e qualquer anotação que já estivesse lá. Nunca remova ou reescreva uma linha existente.
   - Se nenhum profile novo for encontrado, diga isso ao usuário e não escreva nada.

### Proibições absolutas

- **Nunca leia `~/.aws/credentials`** — só `~/.aws/config`.
- **Nunca grave** `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`, senha,
  token de API ou qualquer segredo na skill gerada.
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
que ele trabalha clonado para dentro dela (`projects/celk`, `projects/dati-mcps`, …), e um
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
