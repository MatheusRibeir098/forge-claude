#!/usr/bin/env python3
"""PreToolUse (Bash): bloqueia invocação do `aws` CLI que seja destrutiva/irreversível ou que
altere identidade — quando a lista de `permissions` (deny por prefixo literal) não pega.

O FURO, MEDIDO NA MÁQUINA
O `Bash(...)` das permissions casa só **prefixo exato**. Qualquer flag global do aws ANTES do
serviço já escapa da regra, porque o texto deixa de começar com o prefixo negado:

    aws s3 rm s3://bucket --recursive        -> bloqueado pela permission (ok)
    aws --profile prod s3 rm s3://bucket     -> PASSA (o prefixo negado é "aws s3 rm", o
                                                 comando começa com "aws --profile")
    aws --region us-east-1 iam delete-role   -> PASSA, mesmo motivo
    aws s3 ls s3://bucket                    -> liberado (correto, é leitura)

`--profile prod` é justamente a forma usada para apontar pra produção — a empresa é parceira
AWS, as contas são reais, e há profile com AdministratorAccess disponível nas máquinas. Lista
de permissions não resolve isso: ela não lê o comando, só compara string. Este hook lê.

O QUE ESTE HOOK FAZ (e o que não faz)
1. Acha TODA invocação do `aws` dentro do comando, não só no início: separadores `&&`, `||`,
   `;`, `|`, parênteses de `$(...)`, nova linha (normalizada pra `;` antes de tokenizar), e
   `bash -c "..."` / `sh -c "..."` / `zsh -c "..."` (o conteúdo da string é rescaneado
   recursivamente, então `$(aws ...)` dentro de um `bash -c` também é achado).
2. Tokeniza com `shlex.shlex(..., punctuation_chars=True)`: isso separa `&&`/`||`/`;`/`|`/`(`/
   `)` como tokens próprios mesmo colados sem espaço, e — crucial pra não dar falso positivo —
   mantém uma string entre aspas como UM token só. É por isso que
   `grep -rn "aws s3 rm" .` NUNCA vira invocação: o token é a string inteira `"aws s3 rm"`,
   nunca o token solto `aws`.
3. Para cada invocação achada, normaliza: descarta as flags globais do aws (`--profile`,
   `--region`, `--output`, `--endpoint-url`, `--cli-connect-timeout`, `--color`,
   `--ca-bundle`, `--query`, `--debug`, `--no-verify-ssl`, `--no-paginate`, `--no-cli-pager`,
   `--no-sign-request`, em forma `--flag valor` ou `--flag=valor`) até achar o serviço
   (primeiro token que não é flag nem valor de flag) e a operação (token seguinte).
4. Decide por serviço + operação:
   - nega operação nomeada destrutiva/irreversível: prefixo `delete-`, `remove-`,
     `terminate-`, `purge-`, `destroy-`, mais os casos nomeados `s3 rm`, `s3 rb`,
     `kms schedule-key-deletion`, `ec2 terminate-instances`,
     `organizations leave-organization`, `organizations close-account`;
   - nega qualquer mutação de identidade: serviço `iam` ou `organizations` com operação que
     não é leitura;
   - libera leitura: `get-*`, `list-*`, `describe-*`, `simulate-*`,
     `generate-credential-report`, `s3 ls`, `s3api head-*` (cobre `sts get-caller-identity`
     via `get-*`);
   - o resto (`create-*`, `update-*`, `put-*`, mutação reversível) não é problema deste hook —
     já está em `ask` nas permissions. Não duplica.
5. Se achar mais de uma invocação no comando, para no primeiro `aws` que for negado — é o
   suficiente pra barrar a execução do comando inteiro.

Nunca filtra por `agent_type`: vale pra sessão-raiz e pra qualquer subagente igual. Payload
ilegível, `command` ausente/vazio, aspas malformadas — silêncio, `sys.exit(0)`. Um hook que
explode é pior que um hook ausente.

Só stdlib. Testes em `tests/test_deny_aws.py`.
"""
import json
import re
import shlex
import sys

FRONTEIRA = {"&&", "||", ";", "|", "(", ")", "$"}

RE_ATRIBUICAO = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

SHELLS_COM_DASH_C = {"bash", "sh", "zsh", "dash", "ash"}

FLAGS_GLOBAIS_COM_VALOR = {
    "--profile", "--region", "--output", "--endpoint-url",
    "--cli-connect-timeout", "--color", "--ca-bundle", "--query",
}
FLAGS_GLOBAIS_BOOL = {
    "--debug", "--no-verify-ssl", "--no-paginate", "--no-cli-pager", "--no-sign-request",
}

PREFIXOS_LEITURA = ("get-", "list-", "describe-", "simulate-")
PREFIXOS_DESTRUTIVOS = ("delete-", "remove-", "terminate-", "purge-", "destroy-")
CASOS_NOMEADOS_DESTRUTIVOS = {
    ("s3", "rm"),
    ("s3", "rb"),
    ("kms", "schedule-key-deletion"),
    ("ec2", "terminate-instances"),
    ("organizations", "leave-organization"),
    ("organizations", "close-account"),
}

PROFUNDIDADE_MAXIMA = 5  # limite de recursão em bash -c aninhado — nunca deve chegar perto disso


def tokenizar(texto):
    """Tokeniza respeitando aspas e separando &&/||/;/|/(/) como tokens próprios.
    None se a string tiver aspas malformadas (não deixa o hook explodir)."""
    try:
        lex = shlex.shlex(texto, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""  # '#' pode aparecer em URL/query — não é comentário aqui
        return list(lex)
    except ValueError:
        return None


def segmentar(tokens):
    """Quebra a lista de tokens em comandos simples, nos separadores de FRONTEIRA."""
    segmentos, atual = [], []
    for tok in tokens:
        if tok in FRONTEIRA:
            if atual:
                segmentos.append(atual)
                atual = []
        else:
            atual.append(tok)
    if atual:
        segmentos.append(atual)
    return segmentos


def normalizar(args):
    """Descarta flags globais do aws (e seus valores) até achar serviço + operação.
    Devolve (servico, operacao, profile) — qualquer um pode vir None."""
    profile = None
    servico = None
    i = 0
    while i < len(args):
        tok = args[i]
        nome, igual, valor = tok.partition("=")
        if igual and nome in FLAGS_GLOBAIS_COM_VALOR:
            if nome == "--profile":
                profile = valor
            i += 1
            continue
        if igual and nome in FLAGS_GLOBAIS_BOOL:
            i += 1
            continue
        if tok in FLAGS_GLOBAIS_COM_VALOR:
            if tok == "--profile" and i + 1 < len(args):
                profile = args[i + 1]
            i += 2
            continue
        if tok in FLAGS_GLOBAIS_BOOL:
            i += 1
            continue
        if tok.startswith("-"):
            # flag global não listada: não sabemos se toma valor — segue sem assumir
            i += 1
            continue
        servico = tok
        i += 1
        break
    operacao = args[i] if i < len(args) else None
    return servico, operacao, profile


def encontrar_invocacoes(texto, _profundidade=0):
    """Acha toda invocação `aws ...` dentro do comando, incluindo dentro de bash -c/$(...)."""
    if _profundidade > PROFUNDIDADE_MAXIMA or not texto:
        return []

    texto = texto.replace("\r\n", "\n").replace("\n", " ; ")
    tokens = tokenizar(texto)
    if tokens is None:
        return []

    achados = []
    for seg in segmentar(tokens):
        s = list(seg)
        while s and RE_ATRIBUICAO.match(s[0]):
            s = s[1:]
        if not s:
            continue

        if s[0] == "aws":
            servico, operacao, profile = normalizar(s[1:])
            achados.append({
                "invocacao": " ".join(s),
                "servico": servico,
                "operacao": operacao,
                "profile": profile,
            })
            continue

        # bash -c "..." / sh -c "..." / sudo bash -c "..." — rescaneia o script embutido
        idx_shell = None
        for idx, tok in enumerate(s):
            base = tok.rsplit("/", 1)[-1]
            if base in SHELLS_COM_DASH_C:
                idx_shell = idx
                break
        if idx_shell is not None and "-c" in s[idx_shell:]:
            idx_c = s.index("-c", idx_shell)
            if idx_c + 1 < len(s):
                achados.extend(encontrar_invocacoes(s[idx_c + 1], _profundidade + 1))

    return achados


def decidir(servico, operacao):
    """Devolve (bloquear: bool, motivo: str|None) para o par serviço/operação já normalizado."""
    if not servico or not operacao:
        return False, None

    # leitura — sempre liberada, mesmo em iam/organizations
    if operacao.startswith(PREFIXOS_LEITURA) or operacao == "generate-credential-report":
        return False, None
    if servico == "s3" and operacao == "ls":
        return False, None
    if servico == "s3api" and operacao.startswith("head-"):
        return False, None

    # destrutiva/irreversível — nomeada ou por prefixo
    if operacao.startswith(PREFIXOS_DESTRUTIVOS):
        return True, "operação destrutiva/irreversível"
    if (servico, operacao) in CASOS_NOMEADOS_DESTRUTIVOS:
        return True, "operação destrutiva/irreversível"

    # muda identidade/permissões — iam ou organizations fora do que já é leitura
    if servico in ("iam", "organizations"):
        return True, "operação que altera identidade/permissões (IAM/Organizations) e não é leitura"

    # mutação reversível (create-/update-/put-/modify-...) — problema do `ask`, não deste hook
    return False, None


def montar_razao(achado, motivo):
    partes = [
        f"Hook deny-aws-destrutivo bloqueou `{achado['invocacao']}` — serviço "
        f"`{achado['servico']}`, operação `{achado['operacao']}` ({motivo})."
    ]
    if achado["profile"]:
        partes.append(
            f"O comando usava --profile {achado['profile']} — confira se é mesmo essa a "
            "conta antes de qualquer coisa."
        )
    partes.append(
        "As permissions do plugin negam por prefixo literal e não pegam flags globais antes "
        "do serviço (--profile, --region...); este hook lê o comando de verdade pra fechar "
        "esse furo. Descreva a ação ao usuário e deixe que ele mesmo rode o comando."
    )
    return " ".join(partes)


def main():
    try:
        bruto = sys.stdin.read()
        payload = json.loads(bruto) if bruto else {}
        comando = (payload.get("tool_input") or {}).get("command")
        if not isinstance(comando, str) or not comando.strip():
            sys.exit(0)

        for achado in encontrar_invocacoes(comando):
            bloquear, motivo = decidir(achado["servico"], achado["operacao"])
            if bloquear:
                print(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": montar_razao(achado, motivo),
                }}))
                sys.exit(0)
    except Exception:
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
