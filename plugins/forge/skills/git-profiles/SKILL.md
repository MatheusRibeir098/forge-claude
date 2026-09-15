---
name: git-profiles
description: Use antes de qualquer operação git ou GitHub — descobrir quais contas existem na máquina, escolher a correta com o usuário e aplicar com gh auth switch e git config. Evita commitar ou criar repositório com a identidade errada.
---

# Perfis Git/GitHub

Muita gente tem mais de uma conta na mesma máquina (pessoal e trabalho). Commitar ou criar
repositório com a identidade errada é fácil de fazer e chato de desfazer — esta skill existe
para isso não acontecer.

## 1. Descubra o que existe (nunca chute)

```bash
gh auth status                    # contas autenticadas e qual está ativa
git config --get user.email       # identidade efetiva neste repo
git config --local --get user.email   # há override local?
```

Se o repositório tem override local, ele **vence** o global — é o sinal mais forte sobre qual
identidade aquele projeto espera.

## 2. Regra OBRIGATÓRIA — pergunte

Se o usuário não disse qual perfil usar, **pergunte antes de agir**, listando o que o
`gh auth status` devolveu:

```
Qual conta usar?
1. <conta-A>  (ativa no gh)
2. <conta-B>
```

Se ele já informou ("cria na pessoal", "commita como trabalho"), use direto, sem perguntar.

## 3. Aplique

```bash
# trocar a conta ativa do gh ANTES de criar repo / abrir PR / issue
gh auth switch --user <conta>

# identidade dos commits — sempre --local, por repositório
git config --local user.name  "<nome>"
git config --local user.email "<email>"
```

Fluxo completo ao criar um repositório:

1. `gh auth switch --user <conta>`
2. `gh repo create <nome> --public|--private`
3. `git config --local user.name/user.email` com a identidade daquele perfil
4. Confirme com `git log -1 --format='%an <%ae>'` antes de seguir

## 4. Confira depois

`gh auth switch` muda a conta do `gh`, **não** muda `user.email` dos commits — e vice-versa.
São dois ajustes independentes; é comum acertar um e esquecer o outro. Depois do primeiro
commit, valide:

```bash
git log -1 --format='%an <%ae>'
gh auth status | grep -i 'active account' -B2
```

## Mapa local de perfis (opcional)

Se existir `.claude/git-profiles.local.md` na raiz do projeto, leia-o: é onde o dono da
máquina anota quais contas tem e para que serve cada uma. O arquivo é **local e não
versionado** — identidade de quem usa a ferramenta não entra no repositório da ferramenta.

Formato sugerido:

```markdown
| Apelido | GitHub user | Nome | Email | Quando usar |
|---|---|---|---|---|
| pessoal | <user> | <nome> | <email> | projetos próprios |
| trabalho | <user> | <nome> | <email> | repos da empresa |
```
