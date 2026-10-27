#!/usr/bin/env python3
"""PreToolUse (Bash, sessão principal E subagentes): nega `git commit` em repositório sem
identidade git LOCAL (`user.email` em `git config --local`).

POR QUE EXISTE: há o risco de commits de repositórios pessoais saírem com o e-mail global da
empresa. Quem escolhe o perfil é o usuário (skill `git-profiles`) — o agente não pode cair
silenciosamente na identidade global.

COMO DECIDE, para cada `git commit` do comando (strings entre aspas são ignoradas: `grep "git
commit"` não é invocação):
  1. repositório = `git -C <dir>` se houver; senão o `cd <dir>` anterior no mesmo comando
     encadeado; senão o `cwd` do payload;
  2. roda `git -C <dir> config --local user.email`;
  3. e-mail vazio/ausente (exit 1 do git) => NEGA;
  4. não é repo, diretório inexistente, timeout ou qualquer falha => silêncio (exit 0).
Worktrees compartilham a config do repo principal, então a config local do principal vale.

Identidade explícita no próprio comando conta como identidade: `git -c user.email=x commit` e
`GIT_AUTHOR_EMAIL=x`/`GIT_COMMITTER_EMAIL=x` como prefixo — é escolha deliberada, não a global.

NUNCA QUEBRA A CHAMADA: comando ilegível ou qualquer exceção => exit 0 sem saída. Só emite
`permissionDecision: deny`; nunca `updatedInput`.
"""
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from shell_tokens import (  # noqa: E402
    novo_cwd_do_cd, resolve, segmentos, sem_prefixos, tokeniza,
)

_TIMEOUT_SEGUNDOS = 10
_ENV_IDENTIDADE = ("GIT_AUTHOR_EMAIL=", "GIT_COMMITTER_EMAIL=")


def _le_invocacao_git(args, cwd):
    """(subcomando, cwd efetivo, identidade explícita?) de `git [opções globais] sub ...`."""
    explicita, i = False, 0
    while i < len(args):
        a = args[i]
        if a == "-C" and i + 1 < len(args):
            cwd = resolve(args[i + 1], cwd)
            i += 2
        elif a == "-c" and i + 1 < len(args):
            explicita = explicita or args[i + 1].lower().startswith("user.email=")
            i += 2
        elif a.startswith("-"):
            i += 1
        else:
            return a, cwd, explicita
    return None, cwd, explicita


def repos_com_commit(comando, cwd_inicial):
    """Diretórios onde cada `git commit` do comando vai rodar (sem identidade explícita)."""
    cwd, repos = cwd_inicial, []
    for segmento in segmentos(tokeniza(comando)):
        atribuicoes, resto = sem_prefixos(segmento)
        if not resto:
            continue
        nome = os.path.basename(resto[0])
        if nome == "cd":
            cwd = novo_cwd_do_cd(resto[1:], cwd)
        elif nome == "git":
            sub, dir_repo, explicita = _le_invocacao_git(resto[1:], cwd)
            env_explicito = any(a.startswith(_ENV_IDENTIDADE) for a in atribuicoes)
            if sub == "commit" and not explicita and not env_explicito:
                repos.append(dir_repo)
    return repos


def sem_email_local(dir_repo):
    """True só quando o git confirma um repo SEM user.email local; falha => False (silêncio)."""
    try:
        r = subprocess.run(["git", "-C", dir_repo, "config", "--local", "user.email"],
                           capture_output=True, text=True, timeout=_TIMEOUT_SEGUNDOS)
    except Exception:
        return False
    if r.returncode == 0:
        return not r.stdout.strip()
    return r.returncode == 1 and not r.stdout.strip()  # 1 = chave ausente; 128 = não é repo


def _mensagem(dir_repo):
    return (
        f"O repositório {dir_repo} não tem identidade git local (user.email ausente em "
        "`git config --local`). Antes de commitar, pergunte ao usuário qual perfil usar "
        "(skill `git-profiles`) e grave com `git config --local user.name \"<nome>\"` e "
        "`git config --local user.email \"<email>\"`; só então rode o commit. Não use a "
        "identidade global por conta própria."
    )


def main():
    try:
        payload = json.loads(sys.stdin.read())
        comando = (payload.get("tool_input") or {}).get("command")
        if not isinstance(comando, str) or "commit" not in comando:
            return
        cwd = os.path.abspath(payload.get("cwd") or os.getcwd())
        achado = next((d for d in dict.fromkeys(repos_com_commit(comando, cwd))
                       if sem_email_local(d)), None)
    except Exception:
        return  # hook que explode é pior que hook ausente
    if achado is None:
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": _mensagem(achado),
    }}))


if __name__ == "__main__":
    main()
