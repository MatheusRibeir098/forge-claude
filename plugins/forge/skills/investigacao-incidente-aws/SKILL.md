---
name: investigacao-incidente-aws
description: Use ao investigar um incidente ou erro em produção AWS — monta timeline read-only cruzando CloudTrail, CloudWatch e deploys recentes, sem remediar.
---

# Investigação de Incidente AWS

## Se você é o orquestrador: não rode isto você mesmo

Esta é uma investigação do **Fluxo 3** (skill `orchestrator`, seção "Fluxo de
investigação") — o papel principal é o `scout`, não você. `describe-execution`,
`get-execution-history`, `filter-log-events` e afins costumam devolver muito
texto por chamada; rodar essa sequência na sessão principal é o jeito mais
rápido de inflar o contexto que é reenviado a cada turno. Monte um briefing
com o recurso afetado (ARN/nome), a janela de tempo e a pergunta, nomeie esta
skill, e despache um `scout` (ou vários em paralelo, por eixo — CloudTrail,
CloudWatch, deploys). Você recebe só o JSON com evidência e hipótese; o resto
do trabalho abaixo é o que o `scout` executa.

## O trabalho é diagnosticar, não corrigir

Antes de qualquer comando, confirme conta/perfil com `sts get-caller-identity`
(ver `aws-operacoes-seguras`). Toda ação aqui é **leitura**. Mesmo que a causa
pareça óbvia e a correção seja trivial, **não remedie sem autorização explícita**
do usuário — o pedido de investigação não é pedido de fix.

## Monte a timeline em três eixos

1. **Quem fez o quê e quando** — CloudTrail: `lookup-events` filtrando pela
   janela do incidente e pelo recurso afetado (ARN, nome). Procure eventos de
   escrita (`Create*`, `Update*`, `Delete*`, `Put*`) próximos do horário do
   sintoma.
2. **O que quebrou e quando começou** — CloudWatch Logs (erros, stack traces,
   mudança de taxa de erro) e CloudWatch Alarms (histórico de estado, primeiro
   `ALARM`). O primeiro alarme dispara a âncora temporal; não assuma que é a
   causa.
3. **O que mudou pouco antes** — deploys recentes (pipeline, CDK/CloudFormation
   stack events, tags de versão/commit). Cruze o horário do deploy com o início
   do sintoma no CloudWatch.

## Separe observado de inferência

No relatório final, marque explicitamente:
- **Evidência**: o que os logs/eventos mostram, com timestamp e fonte.
- **Hipótese**: a explicação que a evidência sugere, mas que não foi provada
  (ex.: nenhum log confirma a linha de código exata).

Não apresente hipótese como fato. Se a evidência é insuficiente para uma causa
única, diga isso e liste as hipóteses concorrentes.

## Armadilhas

- **Sintoma vs. causa**: um alarme de erro 500 é sintoma; a causa pode estar
  duas camadas abaixo (ex.: throttling num serviço dependente). Suba a timeline
  até achar o primeiro evento anômalo, não o mais visível.
- **Parar na primeira correlação plausível**: um deploy 10 minutos antes do
  incidente é suspeito, mas não é prova — confirme que o deploy tocou o
  componente que falhou antes de apontá-lo como causa. Descarte-o
  explicitamente se a evidência não sustentar.
