export const meta = {
  name: 'investigar',
  description: 'Investiga uma pergunta em várias frentes com forge:scout, tenta refutar cada achado e devolve só o que resistiu, mais as lacunas',
  whenToUse: 'Quando o Forge precisa de uma resposta confiável que cruza várias partes de um código ou de uma documentação e quer cada achado checado por um scout cético antes de chegar à sessão-raiz',
  phases: [
    { title: 'Varredura', detail: 'um forge:scout por frente' },
    { title: 'Verificação', detail: 'um forge:scout cético por achado (até 8 por frente) tenta refutá-lo lendo o lugar citado' },
    { title: 'Completude', detail: 'um forge:scout aponta o que a pergunta pede e os achados confirmados não cobrem' },
  ],
}

const LIMITE_ACHADOS_POR_FRENTE = 8
const FASE_VARREDURA = 'Varredura'
const FASE_VERIFICACAO = 'Verificação'
const FASE_COMPLETUDE = 'Completude'

const LISTA_DE_TEXTOS = { type: 'array', items: { type: 'string' } }

const SCOUT_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['OK', 'PARCIAL'] },
    resposta: { type: 'string' },
    achados: {
      type: 'array',
      items: {
        type: 'object',
        properties: { o_que: { type: 'string' }, onde: { type: 'string' }, detalhe: { type: 'string' } },
        required: ['o_que', 'onde'],
      },
    },
    caminhos_relevantes: LISTA_DE_TEXTOS,
    nao_encontrado: LISTA_DE_TEXTOS,
    observacoes: LISTA_DE_TEXTOS,
  },
  required: ['status', 'resposta', 'achados'],
}

const REFUTACAO_SCHEMA = {
  type: 'object',
  properties: {
    refutado: { type: 'boolean' },
    motivo: { type: 'string' },
    evidencia: { type: 'string' },
  },
  required: ['refutado', 'motivo', 'evidencia'],
}

const LACUNAS_SCHEMA = {
  type: 'object',
  properties: { lacunas: LISTA_DE_TEXTOS },
  required: ['lacunas'],
}

function lerEntrada(entrada) {
  const pergunta = entrada?.pergunta
  const frentes = entrada?.frentes
  if (typeof pergunta !== 'string' || pergunta.trim() === '') throw new Error('args.pergunta precisa ser um texto não vazio')
  if (!Array.isArray(frentes) || frentes.length === 0) throw new Error('args.frentes precisa ser uma lista não vazia')
  const invalidas = frentes.filter((frente) => !frente?.titulo || !frente.escopo)
  if (invalidas.length > 0) throw new Error('toda frente precisa de titulo e escopo')
  return { pergunta, frentes }
}

function descreverAchado(achado) {
  return [`- o que: ${achado.o_que}`, `- onde: ${achado.onde}`, `- detalhe: ${achado.detalhe ?? '(sem detalhe)'}`].join('\n')
}

function montarPromptVarredura(frente) {
  return [
    `Pergunta da investigação: ${pergunta}`,
    `Frente: ${frente.titulo}\nEscopo: ${frente.escopo}`,
    'Investigue só este escopo. Cada achado precisa de um `onde` verificável (caminho:linha ou URL): outro agente vai abrir esse lugar para tentar refutá-lo.',
    'Não invente caminho nem conteúdo. O que não achar vai em `nao_encontrado`.',
  ].join('\n\n')
}

async function varrerFrente(frente) {
  const varredura = await agent(montarPromptVarredura(frente), {
    label: `varredura · ${frente.titulo}`,
    phase: FASE_VARREDURA,
    agentType: 'forge:scout',
    schema: SCOUT_SCHEMA,
  })
  log(`${frente.titulo}: varredura → ${varredura ? `${varredura.achados.length} achado(s)` : 'sem retorno (null)'}`)
  return varredura
}

function montarPromptRefutacao(achado, frente) {
  return [
    'Você é um verificador cético. Seu papel é REFUTAR o achado abaixo, não confirmá-lo.',
    `Pergunta da investigação: ${pergunta}\nFrente: ${frente.titulo}`,
    `Achado:\n${descreverAchado(achado)}`,
    'Abra e leia o lugar citado em `onde`. Marque `refutado: true` se o lugar não existe, se não diz o que o achado afirma ou se o achado não responde à pergunta. Marque `refutado: false` só se o que você leu sustenta o achado.',
    'Em `evidencia`, cite o trecho lido (curto) ou diga por que não o encontrou.',
  ].join('\n\n')
}

async function refutarAchado(achado, frente, indice) {
  const veredito = await agent(montarPromptRefutacao(achado, frente), {
    label: `refutar · ${frente.titulo} #${indice + 1}`,
    phase: FASE_VERIFICACAO,
    agentType: 'forge:scout',
    schema: REFUTACAO_SCHEMA,
  })
  const desfecho = veredito ? (veredito.refutado ? 'refutado' : 'confirmado') : 'não verificado (null)'
  log(`${frente.titulo}: achado #${indice + 1} (${achado.onde}) → ${desfecho}`)
  return veredito
}

function classificarAchados(achados, vereditos) {
  const classificados = { confirmados: [], refutados: [], naoVerificados: [] }
  achados.forEach((achado, indice) => {
    const veredito = vereditos[indice]
    if (!veredito) classificados.naoVerificados.push(achado)
    else if (veredito.refutado) classificados.refutados.push({ ...achado, motivo_refutacao: veredito.motivo })
    else classificados.confirmados.push(achado)
  })
  return classificados
}

function frenteSemResultado(frente) {
  log(`${frente.titulo}: sem varredura, frente volta vazia`)
  return { titulo: frente.titulo, resposta: null, achados_confirmados: [], achados_refutados: [], achados_nao_verificados: [] }
}

async function verificarFrente(varredura, frente) {
  if (!varredura) return frenteSemResultado(frente)
  const aVerificar = varredura.achados.slice(0, LIMITE_ACHADOS_POR_FRENTE)
  const foraDoTeto = varredura.achados.slice(LIMITE_ACHADOS_POR_FRENTE)
  if (foraDoTeto.length > 0) {
    log(`${frente.titulo}: ${foraDoTeto.length} achado(s) além do teto de ${LIMITE_ACHADOS_POR_FRENTE} ficaram sem verificação: ${foraDoTeto.map((achado) => achado.onde).join(', ')}`)
  }
  const vereditos = await parallel(aVerificar.map((achado, indice) => () => refutarAchado(achado, frente, indice)))
  const { confirmados, refutados, naoVerificados } = classificarAchados(aVerificar, vereditos)
  return {
    titulo: frente.titulo,
    resposta: varredura.resposta,
    achados_confirmados: confirmados,
    achados_refutados: refutados,
    achados_nao_verificados: [...naoVerificados, ...foraDoTeto],
  }
}

function montarPromptCompletude(frentesApuradas) {
  const confirmados = frentesApuradas.map((frente) => ({ frente: frente.titulo, achados: frente.achados_confirmados }))
  const naoVerificados = frentesApuradas.flatMap((frente) => frente.achados_nao_verificados)
  return [
    `Pergunta da investigação: ${pergunta}`,
    `Achados confirmados por verificação:\n${JSON.stringify(confirmados, null, 2)}`,
    `Achados que ninguém conseguiu verificar (não contam como resposta):\n${JSON.stringify(naoVerificados, null, 2)}`,
    'Liste as lacunas: o que a pergunta pede e os achados confirmados não respondem. Não repita o que já está coberto. Sem lacunas, devolva lista vazia.',
  ].join('\n\n')
}

async function levantarLacunas(frentesApuradas) {
  const retorno = await agent(montarPromptCompletude(frentesApuradas), {
    label: 'completude',
    phase: FASE_COMPLETUDE,
    agentType: 'forge:scout',
    schema: LACUNAS_SCHEMA,
  })
  log(`completude → ${retorno ? `${retorno.lacunas.length} lacuna(s)` : 'sem retorno (null), lacunas não levantadas'}`)
  return retorno?.lacunas ?? null
}

const { pergunta, frentes } = lerEntrada(args)
log(`investigação em ${frentes.length} frente(s)`)

const resultadosPorFrente = await pipeline(frentes, varrerFrente, verificarFrente)
const frentesApuradas = resultadosPorFrente.map((resultado, indice) => resultado ?? frenteSemResultado(frentes[indice]))
const lacunas = await levantarLacunas(frentesApuradas)

return { pergunta, frentes: frentesApuradas, lacunas }
