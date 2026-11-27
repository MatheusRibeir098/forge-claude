export const meta = {
  name: 'executar-lote',
  description: 'Roda um lote de tarefas no ciclo forge:dev → forge:tester, com correção automática, e devolve só o resultado final de cada tarefa',
  whenToUse: 'Quando o Forge já tem os briefings de dev e tester de uma ou mais tarefas e quer o ciclo implementar → validar → corrigir dirigido por código, sem a sessão-raiz carregar cada retorno intermediário',
  phases: [
    { title: 'Implementação', detail: 'um forge:dev por tarefa; na correção, ele recebe as falhas e a recomendação do tester' },
    { title: 'Validação', detail: 'um forge:tester por tarefa (browser em fila, contrato em paralelo até max_paralelo); com revisao: true, um forge:scout revisor lê o diff em paralelo ao tester' },
  ],
}

// Argumentos (args):
//   tarefas       lista de { id, briefing_dev, teste: 'browser'|'contrato'|'nenhum', briefing_tester (se teste ≠ nenhum),
//                 revisao?: boolean, briefing_revisor?: string }
//   max_tentativas  inteiro ≥ 1 (padrão 3): quantas vezes o dev recebe a tarefa antes de desistir
//   max_paralelo    inteiro (padrão 6, mínimo 1, corte duro em 16): quantos forge:dev rodam ao mesmo tempo, quantos
//                   forge:tester de contrato rodam ao mesmo tempo e quantos revisores rodam ao mesmo tempo. O tester
//                   browser segue em fila de 1 (há um Chrome só), independente deste valor. Se passar de max_total,
//                   vale max_total (o log avisa).
//   max_total       inteiro (padrão 12, mínimo 1, corte duro em 16, o limite de agentes simultâneos de um Workflow):
//                   teto GLOBAL de chamadas agent() em andamento no lote, somando dev, tester (contrato e browser) e
//                   revisor.
//
// Ordem de aquisição das vagas, sempre a mesma: primeiro a vaga do papel (dev, tester de contrato, revisor ou a fila
// do Chrome) e só depois a vaga global, segurada apenas durante a chamada agent(). Quem segura a vaga global não espera
// nenhuma outra vaga (o dev de correção só pede a sua depois que a chamada anterior soltou tudo), então não há deadlock.
//
// revisao: true dispara, depois do dev entregar e em paralelo ao tester, um forge:scout revisor que lê o diff contra o
// aceite e devolve { achados: [{ onde, problema, gravidade }] }. Os achados entram em resultado.revisao. Se o tester
// der FALHOU, vão junto com as falhas para o dev na correção. O revisor não aprova nem reprova (o veredito é do
// tester, status_final não depende dele) e um revisor sem retorno é ignorado (revisao: null).
// briefing_revisor, se vier, substitui o texto de abertura; a lista de arquivos alterados é sempre anexada.
//
// Todos os forge:dev do lote compartilham a mesma árvore de trabalho: não há worktree por dev neste workflow.
// A proteção contra colisão é a disjunção de arquivos entre as tarefas, que quem monta o lote precisa garantir.

const MAX_TENTATIVAS_PADRAO = 3
const MAX_PARALELO_PADRAO = 6
const MAX_PARALELO_MINIMO = 1
const MAX_PARALELO_TETO = 16
const MAX_TOTAL_PADRAO = 12
const MAX_TOTAL_MINIMO = 1
const MAX_TOTAL_TETO = 16
const MODOS_DE_TESTE = ['browser', 'contrato', 'nenhum']
const FASE_IMPLEMENTACAO = 'Implementação'
const FASE_VALIDACAO = 'Validação'

const LISTA_DE_TEXTOS = { type: 'array', items: { type: 'string' } }

const DEV_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['OK', 'PARCIAL', 'BLOQUEADO'] },
    arquivos_alterados: LISTA_DE_TEXTOS,
    entregaveis: LISTA_DE_TEXTOS,
    build_ok: { type: 'boolean' },
    so_falta_validacao: { type: 'boolean' },
    comandos_para_subir: LISTA_DE_TEXTOS,
    resumo: { type: 'string' },
    feito: LISTA_DE_TEXTOS,
    falta: LISTA_DE_TEXTOS,
    proximo_briefing: { type: 'string' },
    pendencias: LISTA_DE_TEXTOS,
  },
  required: ['status', 'arquivos_alterados', 'build_ok', 'so_falta_validacao', 'comandos_para_subir', 'resumo'],
}

const TESTER_SCHEMA = {
  type: 'object',
  properties: {
    modo: { type: 'string', enum: ['browser', 'contrato'] },
    veredito: { type: 'string', enum: ['PASSOU', 'FALHOU', 'BLOQUEADO'] },
    falhas: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          tipo: { type: 'string', enum: ['build', 'e2e', 'visual', 'api', 'contrato'] },
          onde: { type: 'string' },
          viewport: { type: 'string', enum: ['desktop', 'mobile', 'n/a'] },
          descricao: { type: 'string' },
        },
        required: ['tipo', 'onde', 'descricao'],
      },
    },
    bloqueio: {
      type: 'object',
      properties: { o_que_impediu: { type: 'string' }, o_que_destravaria: { type: 'string' } },
    },
    evidencias: LISTA_DE_TEXTOS,
    logs_relevantes: LISTA_DE_TEXTOS,
    recomendacao_para_dev: { type: 'string' },
  },
  required: ['modo', 'veredito', 'falhas'],
}

const REVISOR_SCHEMA = {
  type: 'object',
  properties: {
    achados: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          onde: { type: 'string' },
          problema: { type: 'string' },
          gravidade: { type: 'string', enum: ['alta', 'media', 'baixa'] },
        },
        required: ['onde', 'problema', 'gravidade'],
        additionalProperties: false,
      },
    },
  },
  required: ['achados'],
}

let filaDoChrome = Promise.resolve()

function lerTarefas(entrada) {
  const tarefas = entrada?.tarefas
  if (!Array.isArray(tarefas) || tarefas.length === 0) {
    throw new Error('args.tarefas precisa ser uma lista não vazia')
  }
  const invalidas = tarefas.filter((tarefa) => !isTarefaValida(tarefa))
  if (invalidas.length > 0) {
    const ids = invalidas.map((tarefa) => tarefa?.id ?? '(sem id)').join(', ')
    throw new Error(`tarefas inválidas: ${ids}. Exigido: id, briefing_dev, teste browser|contrato|nenhum, briefing_tester quando teste ≠ nenhum, revisao booleano e briefing_revisor texto, se presentes`)
  }
  return tarefas
}

function isTarefaValida(tarefa) {
  if (!tarefa?.id || !tarefa.briefing_dev || !MODOS_DE_TESTE.includes(tarefa.teste)) return false
  if (tarefa.revisao !== undefined && typeof tarefa.revisao !== 'boolean') return false
  if (tarefa.briefing_revisor !== undefined && typeof tarefa.briefing_revisor !== 'string') return false
  return tarefa.teste === 'nenhum' || Boolean(tarefa.briefing_tester)
}

function lerMaxTentativas(entrada) {
  const valor = entrada?.max_tentativas
  if (valor === undefined) return MAX_TENTATIVAS_PADRAO
  if (!Number.isInteger(valor) || valor < 1) throw new Error('args.max_tentativas precisa ser um inteiro ≥ 1')
  return valor
}

// Aceita qualquer número inteiro e o corta para [minimo, teto]; só rejeita o que não é inteiro.
function lerLimite(entrada, nome, { padrao, minimo, teto }) {
  const valor = entrada?.[nome]
  if (valor === undefined) return padrao
  if (!Number.isInteger(valor)) throw new Error(`args.${nome} precisa ser um inteiro`)
  const limitado = Math.min(teto, Math.max(minimo, valor))
  if (limitado !== valor) log(`${nome} ${valor} fora de ${minimo}–${teto}, usando ${limitado}`)
  return limitado
}

function lerMaxTotal(entrada) {
  return lerLimite(entrada, 'max_total', { padrao: MAX_TOTAL_PADRAO, minimo: MAX_TOTAL_MINIMO, teto: MAX_TOTAL_TETO })
}

// O limite por papel nunca passa do global: o que sobrar só ficaria esperando a vaga global.
function lerMaxParalelo(entrada, maxTotal) {
  const valor = lerLimite(entrada, 'max_paralelo', { padrao: MAX_PARALELO_PADRAO, minimo: MAX_PARALELO_MINIMO, teto: MAX_PARALELO_TETO })
  if (valor <= maxTotal) return valor
  if (entrada?.max_paralelo !== undefined) log(`max_paralelo ${valor} acima de max_total ${maxTotal}, usando ${maxTotal}`)
  return maxTotal
}

// Semáforo em JS puro: no máximo `limite` execuções ao mesmo tempo, as demais esperam em ordem de chegada.
function criarSemaforo(limite) {
  let ativos = 0
  const esperando = []
  return async function comVaga(executar) {
    while (ativos >= limite) await new Promise((liberar) => esperando.push(liberar))
    ativos += 1
    try {
      return await executar()
    } finally {
      ativos -= 1
      esperando.shift()?.()
    }
  }
}

// Toda chamada agent() do lote passa por aqui: a vaga global é a última a ser pedida e a primeira a ser solta.
function agentNoTeto(prompt, opcoes) {
  return comVagaGlobal(() => agent(prompt, opcoes))
}

function comExclusividadeDoChrome(executar) {
  const resultado = filaDoChrome.then(executar)
  // A fila avança mesmo se esta execução falhar; o erro continua chegando ao chamador por `resultado`.
  filaDoChrome = resultado.then(avancarFila, avancarFila)
  return resultado
}

function avancarFila() {}

function listarEmMarkdown(itens) {
  if (!itens?.length) return '- (nenhum informado)'
  return itens.map((item) => `- ${item}`).join('\n')
}

async function rodarDev(tarefa, briefing, tentativa) {
  const dev = await comVagaDeDev(() => agentNoTeto(briefing, {
    label: `${tarefa.id} · dev #${tentativa}`,
    phase: FASE_IMPLEMENTACAO,
    agentType: 'forge:dev',
    schema: DEV_SCHEMA,
  }))
  log(`${tarefa.id}: dev #${tentativa} → ${dev?.status ?? 'sem retorno (null)'}`)
  return dev
}

function montarPromptTester(tarefa, dev) {
  const secoes = [
    tarefa.briefing_tester,
    `## Modo\n${tarefa.teste}`,
    `## Arquivos alterados pelo dev\n${listarEmMarkdown(dev.arquivos_alterados)}`,
    `## Comandos para subir\n${listarEmMarkdown(dev.comandos_para_subir)}`,
  ]
  if (dev.falta?.length) secoes.push(`## O dev não verificou\n${listarEmMarkdown(dev.falta)}`)
  return secoes.join('\n\n')
}

async function rodarTester(tarefa, dev, tentativa) {
  const chamarTester = () => agentNoTeto(montarPromptTester(tarefa, dev), {
    label: `${tarefa.id} · tester #${tentativa}`,
    phase: FASE_VALIDACAO,
    agentType: 'forge:tester',
    schema: TESTER_SCHEMA,
  })
  const isBrowser = tarefa.teste === 'browser'
  if (isBrowser) log(`${tarefa.id}: tester #${tentativa} na fila do Chrome`)
  const tester = isBrowser ? await comExclusividadeDoChrome(chamarTester) : await comVagaDeTesterDeContrato(chamarTester)
  log(`${tarefa.id}: tester #${tentativa} → ${tester?.veredito ?? 'sem retorno (null)'}`)
  return tester
}

function montarPromptRevisor(tarefa, dev) {
  const abertura = tarefa.briefing_revisor
    ?? `Revise a entrega da tarefa ${tarefa.id} contra o aceite abaixo. Procure erros de lógica, requisitos não atendidos, regressões e riscos de segurança.\n\n## Briefing e aceite da tarefa\n${tarefa.briefing_dev}`
  const secoes = [
    abertura,
    `## Arquivos alterados pelo dev\n${listarEmMarkdown(dev.arquivos_alterados)}`,
    '## Como revisar\nLeia o diff desses arquivos (somente leitura, não altere nada) e compare com o aceite. Você não aprova nem reprova: o veredito é do tester. Devolva só achados concretos, com `arquivo:linha` em `onde`; sem achados, devolva a lista vazia.',
  ]
  if (dev.resumo) secoes.push(`## Resumo do dev\n${dev.resumo}`)
  return secoes.join('\n\n')
}

// Revisor é consultivo: sem retorno (null ou erro) vira null e a tarefa segue sem ele.
async function rodarRevisor(tarefa, dev, tentativa) {
  try {
    const revisao = await comVagaDeRevisor(() => agentNoTeto(montarPromptRevisor(tarefa, dev), {
      label: `${tarefa.id} · revisor #${tentativa}`,
      phase: FASE_VALIDACAO,
      agentType: 'forge:scout',
      schema: REVISOR_SCHEMA,
    }))
    log(`${tarefa.id}: revisor #${tentativa} → ${revisao ? `${revisao.achados?.length ?? 0} achado(s)` : 'sem retorno (null)'}`)
    return Array.isArray(revisao?.achados) ? revisao.achados : null
  } catch (erro) {
    log(`${tarefa.id}: revisor #${tentativa} falhou e foi ignorado: ${erro?.message ?? erro}`)
    return null
  }
}

async function validarERevisar(tarefa, dev, tentativa) {
  const [tester, revisao] = await Promise.all([
    rodarTester(tarefa, dev, tentativa),
    tarefa.revisao ? rodarRevisor(tarefa, dev, tentativa) : null,
  ])
  return { tester, revisao }
}

function montarBriefingCorrecao(tarefa, dev, tester, tentativa, revisao) {
  const secoes = [
    tarefa.briefing_dev,
    `## Correção pedida pelo tester (tentativa ${tentativa + 1})`,
    'A entrega anterior foi reprovada na validação. Corrija o que as falhas abaixo apontam, sem refazer o que já funciona.',
    `### Arquivos alterados na tentativa anterior\n${listarEmMarkdown(dev.arquivos_alterados)}`,
    `### Falhas\n${JSON.stringify(tester.falhas ?? [], null, 2)}`,
    `### Recomendação do tester\n${tester.recomendacao_para_dev ?? '(sem recomendação)'}`,
  ]
  if (revisao?.length) secoes.push(`### Achados do revisor (leia contra as falhas; confirme antes de mexer)\n${JSON.stringify(revisao, null, 2)}`)
  return secoes.join('\n\n')
}

// PARCIAL com código pronto e build verde, a que só falta a validação que o dev não pode fazer (ver a UI, abrir o navegador).
function isProntoParaValidar(tarefa, dev) {
  return dev.status === 'PARCIAL' && dev.so_falta_validacao === true && dev.build_ok === true && tarefa.teste !== 'nenhum'
}

// Devolve o status final quando o ciclo termina no dev; null quando segue para o tester.
function encerramentoAposDev(tarefa, dev) {
  if (!dev) return 'BLOQUEADO'
  if (isProntoParaValidar(tarefa, dev)) {
    log(`${tarefa.id}: dev PARCIAL só de validação com build ok, seguindo para o tester`)
    return null
  }
  if (dev.status !== 'OK') return dev.status
  if (tarefa.teste === 'nenhum') return 'SEM_TESTE'
  return null
}

function montarResultado(tarefa, { statusFinal, tentativas, dev, tester, revisao }) {
  log(`${tarefa.id}: encerrada → ${statusFinal} em ${tentativas} tentativa(s)`)
  return {
    id: tarefa.id,
    status_final: statusFinal,
    tentativas,
    dev,
    tester,
    revisao: revisao ?? null,
    falta_do_dev: dev?.falta ?? [],
    proximo_briefing: dev?.proximo_briefing ?? null,
  }
}

async function executarTarefa(tarefa) {
  let briefing = tarefa.briefing_dev
  let tester = null
  let revisao = null
  for (let tentativa = 1; tentativa <= maxTentativas; tentativa++) {
    const dev = await rodarDev(tarefa, briefing, tentativa)
    const paradaNoDev = encerramentoAposDev(tarefa, dev)
    if (paradaNoDev) {
      if (paradaNoDev === 'SEM_TESTE' && tarefa.revisao) revisao = await rodarRevisor(tarefa, dev, tentativa)
      return montarResultado(tarefa, { statusFinal: paradaNoDev, tentativas: tentativa, dev, tester, revisao })
    }
    const validacao = await validarERevisar(tarefa, dev, tentativa)
    tester = validacao.tester
    revisao = validacao.revisao
    const veredito = tester?.veredito ?? 'BLOQUEADO'
    if (veredito !== 'FALHOU' || tentativa === maxTentativas) {
      return montarResultado(tarefa, { statusFinal: veredito, tentativas: tentativa, dev, tester, revisao })
    }
    log(`${tarefa.id}: reprovada, pedindo correção ao dev`)
    briefing = montarBriefingCorrecao(tarefa, dev, tester, tentativa, revisao)
  }
}

function resultadoDeFalhaDoScript(tarefa) {
  log(`${tarefa.id}: o script falhou nesta tarefa; detalhe em /workflows`)
  return { id: tarefa.id, status_final: 'BLOQUEADO', tentativas: null, dev: null, tester: null, revisao: null, falta_do_dev: [], proximo_briefing: null }
}

const tarefas = lerTarefas(args)
const maxTentativas = lerMaxTentativas(args)
const maxTotal = lerMaxTotal(args)
const maxParalelo = lerMaxParalelo(args, maxTotal)
const comVagaGlobal = criarSemaforo(maxTotal)
const comVagaDeDev = criarSemaforo(maxParalelo)
const comVagaDeTesterDeContrato = criarSemaforo(maxParalelo)
const comVagaDeRevisor = criarSemaforo(maxParalelo)
log(`lote com ${tarefas.length} tarefa(s), até ${maxTentativas} tentativa(s) cada, até ${maxParalelo} dev/tester de contrato/revisor simultâneos, até ${maxTotal} agentes ao todo`)

const resultados = await pipeline(tarefas, executarTarefa)
return resultados.map((resultado, indice) => resultado ?? resultadoDeFalhaDoScript(tarefas[indice]))
