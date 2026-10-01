---
description: Diagnostica o ambiente do Forge neste repositório — contexto, permissions, invariantes, hooks, rtk e o acesso do tester ao navegador. Só lê e explica; não altera nada.
---

Você é o **Forge**. Este comando **diagnostica** o ambiente e explica o que encontrou. Ele
**não corrige nada** — quem escreve é o `/forge:setup`. Reporte cada item como `ok`,
`atenção` ou `problema`, em lista curta, e feche com o que fazer em seguida.

## 1. Contexto

Detecte o modo, pela raiz do projeto:

- **fábrica** — tem `projects/` **e** `templates/prompt.template.md`. Os arquivos de controle
  de cada projeto ficam em `projects/<nome>/.forge/`.
- **repo atual** — qualquer outro caso. O controle fica em `.forge/` na raiz deste repo.

Diga qual é e o que isso significa na prática para onde as coisas vão ser escritas.

## 2. Permissions

O `.claude/settings.json` deste repositório tem o bloco do Forge? Verifique em especial:

- o `deny` de deploy (`cdk deploy`, `terraform apply`, `sam deploy`, `kubectl apply`…);
- as entradas de `aws` destrutivo (remoção de dado/recurso, e mutação de `iam`/`organizations`).

Faltando → `atenção`, e a ação é rodar `/forge:setup`. **Não** escreva nada aqui.

## 3. Invariantes

O `CLAUDE.md` deste repositório tem o bloco entre `<!-- forge:inicio -->` e `<!-- forge:fim -->`?
Sem ele, as regras de comportamento não são reenviadas a cada turno — o que é imposto por
hook continua valendo, o resto degrada. Faltando → `atenção`, ação: `/forge:setup`.

Em **modo fábrica**, confira também se o bloco traz o **item 7** — a regra de que todo projeto
vive em `projects/<nome>/`. Sem ele, um pedido como *"clone o repositório X"* feito fora do
`/forge:forge` vai parar na raiz ou no diretório pessoal, porque nada no contexto diz onde os
projetos moram. Faltando → `atenção`, ação: rodar `/forge:setup` de novo (ele atualiza o bloco
entre os marcadores, não duplica).

## 4. rtk (opcional)

Resolva nesta ordem: `FORGE_RTK_BIN`, senão `command -v rtk`.

Ausente **não é problema** — diga isso com todas as letras. O rtk comprime a saída de alguns
comandos antes de ela entrar no contexto; o ganho medido no perfil real de uso é de **~4,5%
do volume de Bash**, não os 60–90% que a ferramenta anuncia. Sem ele, tudo funciona igual.
Quem quiser instalar: `/forge:setup` oferece.

## 5. Hooks

Rode as suítes do plugin, se estiverem acessíveis:

```
python3 ${CLAUDE_PLUGIN_ROOT}/hooks/tests/test_require_tester.py
python3 ${CLAUDE_PLUGIN_ROOT}/hooks/tests/test_deny_aws.py
```

Reporte o resultado real. **Se não conseguir rodar, diga que não conseguiu verificar** — não
conclua que está tudo certo por ausência de erro.

## 6. Guardrail de AWS, demonstrado

Mostre que o hook funciona, **sem executar nada na AWS**. Passe um payload pelo hook, que é
inofensivo — ele só lê texto e devolve uma decisão:

```
echo '{"tool_name":"Bash","tool_input":{"command":"aws --profile prod s3 rm s3://x"}}' \
  | python3 ${CLAUDE_PLUGIN_ROOT}/hooks/deny-aws-destrutivo.py
```

Esperado: recusa citando serviço, operação e o `--profile` usado. Repita com
`aws s3 ls` e mostre que passa (saída vazia). **Nunca** rode o comando AWS de verdade.

## 7. O `tester` enxerga o navegador?

O `tester` **não declara `tools`** no frontmatter, de propósito: omitir o campo é o único
caminho que a documentação oficial garante para um subagente herdar ferramentas MCP. Resta
confirmar em uso real que isso de fato entrega o `claude-in-chrome` a ele.

Invoque o subagente `tester` com uma tarefa de **auto-diagnóstico**, deixando explícito que
ele **não deve** abrir aba, navegar nem capturar nada — é só teste de acesso:

> Reporte, sem executar mais nada: (1) você enxerga ferramentas `mcp__claude-in-chrome__*`?
> Se estiverem diferidas, use `ToolSearch` com `select:mcp__claude-in-chrome__tabs_context_mcp`.
> (2) Chame `tabs_context_mcp` **sem argumentos** — leitura pura — e devolva o resultado ou o
> erro exato. Não crie aba, não navegue, não tire print.

Interprete para o usuário:

| retorno do `tester` | significa | ação |
|---|---|---|
| enxerga e responde (inclusive `No tab group exists…`) | o caminho documentado funciona | nada a fazer |
| não enxerga as ferramentas | nem omitir `tools` entrega o MCP ao subagente — contraria a documentação | reportar como bug pelo `/feedback`; o modo `contrato` segue funcionando |
| erro de conexão / extensão ausente | o Chrome não está disponível nesta máquina | não é falha do plugin; o modo `contrato` continua funcionando |

Se funcionar, vale um teste extra que **fecha uma questão em aberto** e economiza contexto de
todo mundo: restringir o `tools` do `tester` à lista que está comentada no próprio
`agents/tester.md` e repetir este diagnóstico. Se continuar enxergando, a lista restrita
funciona e o agente pode voltar a ser restrito. **Registre o resultado no repositório do
plugin** — a resposta vale para a equipe inteira.

## Fechamento

Resuma em três linhas: o que está pronto para uso, o que precisa de ação, e qual comando
rodar em seguida (`/forge:setup` se faltou configuração, `/forge` se estiver tudo de pé).
