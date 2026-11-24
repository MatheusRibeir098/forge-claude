export const meta = {
  name: 'executar-lote',
  description: 'Roda um lote de tarefas no ciclo forge:dev → forge:tester, com correção automática, e devolve só o resultado final de cada tarefa',
  whenToUse: 'Quando o Forge já tem os briefings de dev e tester de uma ou mais tarefas e quer o ciclo implementar → validar → corrigir dirigido por código, sem a sessão-raiz carregar cada retorno intermediário',
  phases: [
    { title: 'Implementação', detail: 'um forge:dev por tarefa; na correção, ele recebe as falhas e a recomendação do tester' },
    { title: 'Validação', detail: 'um forge:tester por tarefa; testers browser rodam em fila (há um Chrome só), testers contrato em paralelo' },
  ],
}

const MAX_TENTATIVAS_PADRAO = 3
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
    comandos_para_subir: LISTA_DE_TEXTOS,
    resumo: { type: 'string' },
    feito: LISTA_DE_TEXTOS,
    falta: LISTA_DE_TEXTOS,
    proximo_briefing: { type: 'string' },
    pendencias: LISTA_DE_TEXTOS,
  },
  required: ['status', 'arquivos_alterados', 'build_ok', 'comandos_para_subir', 'resumo'],
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

let filaDoChrome = Promise.resolve()

function lerTarefas(entrada) {
  const tarefas = entrada?.tarefas
  if (!Array.isArray(tarefas) || tarefas.length === 0) {
    throw new Error('args.tarefas precisa ser uma lista não vazia')
  }
  const invalidas = tarefas.filter((tarefa) => !isTarefaValida(tarefa))
  if (invalidas.length > 0) {
    const ids = invalidas.map((tarefa) => tarefa?.id ?? '(sem id)').join(', ')
    throw new Error(`tarefas inválidas: ${ids}. Exigido: id, briefing_dev, teste browser|contrato|nenhum e briefing_tester quando teste ≠ nenhum`)
  }
  return tarefas
}

function isTarefaValida(tarefa) {
  if (!tarefa?.id || !tarefa.briefing_dev || !MODOS_DE_TESTE.includes(tarefa.teste)) return false
  return tarefa.teste === 'nenhum' || Boolean(tarefa.briefing_tester)
}

function lerMaxTentativas(entrada) {
  const valor = entrada?.max_tentativas
  if (valor === undefined) return MAX_TENTATIVAS_PADRAO
  if (!Number.isInteger(valor) || valor < 1) throw new Error('args.max_tentativas precisa ser um inteiro ≥ 1')
  return valor
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
  const dev = await agent(briefing, {
    label: `${tarefa.id} · dev #${tentativa}`,
    phase: FASE_IMPLEMENTACAO,
    agentType: 'forge:dev',
    schema: DEV_SCHEMA,
  })
  log(`${tarefa.id}: dev #${tentativa} → ${dev?.status ?? 'sem retorno (null)'}`)
  return dev
}

function montarPromptTester(tarefa, dev) {
  return [
    tarefa.briefing_tester,
    `## Modo\n${tarefa.teste}`,
    `## Arquivos alterados pelo dev\n${listarEmMarkdown(dev.arquivos_alterados)}`,
    `## Comandos para subir\n${listarEmMarkdown(dev.comandos_para_subir)}`,
  ].join('\n\n')
}

async function rodarTester(tarefa, dev, tentativa) {
  const chamarTester = () => agent(montarPromptTester(tarefa, dev), {
    label: `${tarefa.id} · tester #${tentativa}`,
    phase: FASE_VALIDACAO,
    agentType: 'forge:tester',
    schema: TESTER_SCHEMA,
  })
  const isBrowser = tarefa.teste === 'browser'
  if (isBrowser) log(`${tarefa.id}: tester #${tentativa} na fila do Chrome`)
  const tester = isBrowser ? await comExclusividadeDoChrome(chamarTester) : await chamarTester()
  log(`${tarefa.id}: tester #${tentativa} → ${tester?.veredito ?? 'sem retorno (null)'}`)
  return tester
}

function montarBriefingCorrecao(tarefa, dev, tester, tentativa) {
  return [
    tarefa.briefing_dev,
    `## Correção pedida pelo tester (tentativa ${tentativa + 1})`,
    'A entrega anterior foi reprovada na validação. Corrija o que as falhas abaixo apontam, sem refazer o que já funciona.',
    `### Arquivos alterados na tentativa anterior\n${listarEmMarkdown(dev.arquivos_alterados)}`,
    `### Falhas\n${JSON.stringify(tester.falhas ?? [], null, 2)}`,
    `### Recomendação do tester\n${tester.recomendacao_para_dev ?? '(sem recomendação)'}`,
  ].join('\n\n')
}

// Devolve o status final quando o ciclo termina no dev; null quando segue para o tester.
function encerramentoAposDev(tarefa, dev) {
  if (!dev) return 'BLOQUEADO'
  if (dev.status !== 'OK') return dev.status
  if (tarefa.teste === 'nenhum') return 'SEM_TESTE'
  return null
}

function montarResultado(tarefa, { statusFinal, tentativas, dev, tester }) {
  log(`${tarefa.id}: encerrada → ${statusFinal} em ${tentativas} tentativa(s)`)
  return {
    id: tarefa.id,
    status_final: statusFinal,
    tentativas,
    dev,
    tester,
    proximo_briefing: dev?.proximo_briefing ?? null,
  }
}

async function executarTarefa(tarefa) {
  let briefing = tarefa.briefing_dev
  let tester = null
  for (let tentativa = 1; tentativa <= maxTentativas; tentativa++) {
    const dev = await rodarDev(tarefa, briefing, tentativa)
    const paradaNoDev = encerramentoAposDev(tarefa, dev)
    if (paradaNoDev) return montarResultado(tarefa, { statusFinal: paradaNoDev, tentativas: tentativa, dev, tester })
    tester = await rodarTester(tarefa, dev, tentativa)
    const veredito = tester?.veredito ?? 'BLOQUEADO'
    if (veredito !== 'FALHOU' || tentativa === maxTentativas) {
      return montarResultado(tarefa, { statusFinal: veredito, tentativas: tentativa, dev, tester })
    }
    log(`${tarefa.id}: reprovada, pedindo correção ao dev`)
    briefing = montarBriefingCorrecao(tarefa, dev, tester, tentativa)
  }
}

function resultadoDeFalhaDoScript(tarefa) {
  log(`${tarefa.id}: o script falhou nesta tarefa; detalhe em /workflows`)
  return { id: tarefa.id, status_final: 'BLOQUEADO', tentativas: null, dev: null, tester: null, proximo_briefing: null }
}

const tarefas = lerTarefas(args)
const maxTentativas = lerMaxTentativas(args)
log(`lote com ${tarefas.length} tarefa(s), até ${maxTentativas} tentativa(s) cada`)

const resultados = await pipeline(tarefas, executarTarefa)
return resultados.map((resultado, indice) => resultado ?? resultadoDeFalhaDoScript(tarefas[indice]))
