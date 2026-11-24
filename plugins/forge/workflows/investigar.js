export const meta = {
  name: 'investigar',
  description: 'Investiga uma pergunta em várias frentes com forge:scout, tenta refutar cada achado e devolve só o que resistiu, mais as lacunas',
  whenToUse: 'Quando o Forge precisa de uma resposta confiável que cruza várias partes de um código ou de uma documentação e quer cada achado checado por um scout cético antes de chegar à sessão-raiz',
  phases: [
    { title: 'Varredura', detail: 'um forge:scout por frente' },
    { title: 'Verificação', detail: 'um forge:scout cético por frente confere em lote os achados dela (até 8), lendo os lugares citados, e devolve um veredito por achado' },
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
        required: ['o_que', 'onde', 'detalhe'],
        additionalProperties: false,
      },
    },
    caminhos_relevantes: LISTA_DE_TEXTOS,
    nao_encontrado: LISTA_DE_TEXTOS,
    observacoes: LISTA_DE_TEXTOS,
  },
  required: ['status', 'resposta', 'achados'],
}

const VEREDITOS_SCHEMA = {
  type: 'object',
  properties: {
    vereditos: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          indice: { type: 'integer' },
          refutado: { type: 'boolean' },
          motivo: { type: 'string' },
          evidencia: { type: 'string' },
        },
        required: ['indice', 'refutado', 'motivo', 'evidencia'],
      },
    },
  },
  required: ['vereditos'],
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

function descreverAchado(achado, numero) {
  return [`Achado ${numero}`, `- o que: ${achado.o_que}`, `- onde: ${achado.onde}`, `- detalhe: ${achado.detalhe}`].join('\n')
}

function montarPromptVarredura(frente) {
  return [
    `Pergunta da investigação: ${pergunta}`,
    `Frente: ${frente.titulo}\nEscopo: ${frente.escopo}`,
    'Investigue só este escopo. Cada achado precisa de um `onde` verificável (caminho:linha ou URL): outro agente vai abrir esse lugar para tentar refutá-lo.',
    'Cada achado tem exatamente as chaves `o_que`, `onde` e `detalhe`, nenhuma outra.',
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

// Incompletude não é refutação: um fato correto em achados_refutados engana a raiz.
function montarPromptVerificacao(achados, frente) {
  return [
    'Você é um verificador cético. Para cada achado abaixo, abra o lugar citado em `onde` e confira se ele sustenta a afirmação.',
    `Pergunta da investigação: ${pergunta}\nFrente: ${frente.titulo}`,
    `Achados (${achados.length}):\n\n${achados.map((achado, posicao) => descreverAchado(achado, posicao + 1)).join('\n\n')}`,
    'Marque `refutado: true` SÓ quando a afirmação é falsa ou o lugar citado não a sustenta: o arquivo ou a linha não existe, ou o código diz outra coisa. Caso contrário, `refutado: false`.',
    'Achado verdadeiro mas incompleto, ou que não responde à pergunta inteira, NÃO é refutado. Lacuna de cobertura é assunto da fase de completude, não desta.',
    `Devolva um veredito por achado, com \`indice\` igual ao número do achado (1 a ${achados.length}). Leia cada arquivo uma vez só, mesmo que vários achados apontem para ele.`,
    '`evidencia` é obrigatória e pode ser curta: o trecho lido ou "linha X diz Y"; se não encontrou o lugar, diga isso.',
  ].join('\n\n')
}

function indexarVereditos(vereditos, quantidade, frente) {
  const porPosicao = Array.from({ length: quantidade }, () => null)
  for (const veredito of vereditos) {
    const posicao = veredito.indice - 1
    if (!Number.isInteger(veredito.indice) || posicao < 0 || posicao >= quantidade) {
      log(`${frente.titulo}: veredito com índice ${veredito.indice} fora da lista (1 a ${quantidade}), ignorado`)
    } else if (porPosicao[posicao]) {
      log(`${frente.titulo}: veredito repetido para o achado #${veredito.indice}, vale o primeiro`)
    } else {
      porPosicao[posicao] = veredito
    }
  }
  return porPosicao
}

async function verificarEmLote(achados, frente) {
  if (achados.length === 0) return []
  const retorno = await agent(montarPromptVerificacao(achados, frente), {
    label: `verificar · ${frente.titulo}`,
    phase: FASE_VERIFICACAO,
    agentType: 'forge:scout',
    schema: VEREDITOS_SCHEMA,
  })
  if (!retorno) {
    log(`${frente.titulo}: verificação sem retorno (null), ${achados.length} achado(s) ficam não verificados`)
    return []
  }
  return indexarVereditos(retorno.vereditos, achados.length, frente)
}

function classificarAchados(achados, vereditos, frente) {
  const classificados = { confirmados: [], refutados: [], naoVerificados: [] }
  achados.forEach((achado, indice) => {
    const veredito = vereditos[indice]
    if (!veredito) {
      log(`${frente.titulo}: achado #${indice + 1} (${achado.onde}) sem veredito, fica não verificado`)
      classificados.naoVerificados.push(achado)
    } else if (veredito.refutado) {
      classificados.refutados.push({ ...achado, motivo_refutacao: veredito.motivo })
    } else {
      classificados.confirmados.push(achado)
    }
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
  const vereditos = await verificarEmLote(aVerificar, frente)
  const { confirmados, refutados, naoVerificados } = classificarAchados(aVerificar, vereditos, frente)
  log(`${frente.titulo}: verificação → ${confirmados.length} confirmado(s), ${refutados.length} refutado(s), ${naoVerificados.length} não verificado(s)`)
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
