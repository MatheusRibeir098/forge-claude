#!/usr/bin/env python3
"""PreToolUse (Bash, sessão-raiz): se o shell da sessão principal ficou fora da pasta base do
projeto, reescreve o comando para `cd "<raiz>" && <comando original>`.

POR QUE EXISTE: a cwd do shell persiste entre chamadas de Bash. Quando o orquestrador roda um
`cd /outra/pasta` solto para ler algo e não volta, as chamadas seguintes rodam fora da raiz e
as regras/arquivos de `.claude/` da pasta base deixam de valer.

COMPOSIÇÃO COM `rtk-root.sh` — decisão: UM ÚNICO escritor de `updatedInput`.
Hooks PreToolUse do mesmo evento rodam em paralelo e recebem o MESMO comando original; se os
dois reescrevessem, a resposta que terminasse por último venceria e uma reescrita anularia a
outra (a ordem em hooks.json não resolve). Então, quando a cwd está fora da raiz, o
`rtk-root.sh` fica calado e ESTE hook chama o `rtk-root.sh` (com FORGE_VOLTA_COMPOSE=1) só para
descobrir se o rtk reescreveria o comando, e emite `cd "<raiz>" && <comando já com rtk>`. Com a
cwd na raiz este hook não faz nada e o `rtk-root.sh` age sozinho, como antes. Do veredito do
rtk só o comando é aproveitado: o `permissionDecision` dele é descartado de propósito — este
hook nunca devolve `permissionDecision`, para não pular o sistema de permissões.

NUNCA QUEBRA A CHAMADA: qualquer exceção ou payload estranho => exit 0 sem saída.
"""
import json
import os
import subprocess
import sys

RTK_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rtk-root.sh")
RTK_TIMEOUT_SEGUNDOS = 10


def _mesmo_caminho(a: str, b: str) -> bool:
    return os.path.realpath(a) == os.path.realpath(b)


def _entre_aspas(caminho: str) -> str:
    """Aspas duplas do shell, escapando o que ainda é especial dentro delas."""
    for especial in ("\\", '"', "$", "`"):
        caminho = caminho.replace(especial, "\\" + especial)
    return f'"{caminho}"'


def _comando_via_rtk(payload: dict, comando: str) -> str:
    """Comando reescrito pelo rtk-root.sh, ou o original se o rtk não agiu/falhou."""
    try:
        env = dict(os.environ, FORGE_VOLTA_COMPOSE="1")
        resultado = subprocess.run(
            ["bash", RTK_ROOT], input=json.dumps(payload), env=env,
            capture_output=True, text=True, timeout=RTK_TIMEOUT_SEGUNDOS,
        )
        saida = json.loads(resultado.stdout)
        novo = saida["hookSpecificOutput"]["updatedInput"]["command"]
        return novo if isinstance(novo, str) and novo.strip() else comando
    except Exception:
        return comando


def _aviso(cwd: str, raiz: str) -> str:
    return (
        f"[pasta base] o shell estava em {cwd}; voltei para {raiz}. "
        "Use `cd x && cmd` ou caminhos absolutos, não `cd` solto."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
            return 0
        # Mesmo critério dos outros hooks: agent_id/agent_type => subagente, fora do escopo.
        if payload.get("agent_id") or payload.get("agent_type"):
            return 0

        raiz = os.environ.get("CLAUDE_PROJECT_DIR")
        cwd = payload.get("cwd")
        tool_input = payload.get("tool_input")
        if not raiz or not isinstance(cwd, str) or not cwd or not isinstance(tool_input, dict):
            return 0
        comando = tool_input.get("command")
        if not isinstance(comando, str) or not comando.strip():
            return 0
        if _mesmo_caminho(cwd, raiz):
            return 0

        base = _comando_via_rtk(payload, comando)
        novo_input = dict(tool_input, command=f"cd {_entre_aspas(raiz)} && {base}")
        print(json.dumps({
            "systemMessage": _aviso(cwd, raiz),
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "updatedInput": novo_input,
            },
        }, ensure_ascii=False))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
