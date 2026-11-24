// Roda os scripts de workflow fora do Claude Code, com agent/pipeline/parallel falsos.
// Uso: node plugins/forge/workflows/tests/test_workflows.mjs
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const PASTA_WORKFLOWS = join(dirname(fileURLToPath(import.meta.url)), '..')
const AsyncFunction = (async () => {}).constructor
const ATRASO_DO_AGENTE_MS = 5
const DURACAO_DO_TESTER_MS = 20
const APIS_PROIBIDAS = [/Date\.now\(/, /Math\.random\(/, /new Date\(\s*\)/, /\bimport\s*\(/, /\brequire\s*\(/]

function lerScript(nome) {
  return readFileSync(join(PASTA_WORKFLOWS, `${nome}.js`), 'utf8')
}

// Avalia só o literal do meta: se ele citar variável ou chamada, o eval quebra, como no runtime.
function lerMeta(nome) {
  const texto = lerScript(nome)
  const inicio = texto.indexOf('{', texto.indexOf('export const meta'))
  const fim = texto.indexOf('\n}\n', inicio)
  return new Function(`return ${texto.slice(inicio, fim + 2)}`)()
}

function compilarWorkflow(nome) {
  const corpo = lerScript(nome).replace(/^export const meta/m, 'const meta')
  return new AsyncFunction('agent', 'pipeline', 'parallel', 'phase', 'log', 'args', corpo)
}

function esperar(ms) {
  return new Promise((resolver) => setTimeout(resolver, ms))
}

// Mesma semântica do runtime: sem barreira entre estágios e um throw vira null no item.
async function pipelineFalso(itens, ...estagios) {
  return Promise.all(itens.map(async (item, indice) => {
    let anterior = item
    try {
      for (const estagio of estagios) anterior = await estagio(anterior, item, indice)
      return anterior
    } catch {
      return null
    }
  }))
}

async function parallelFalso(tarefas) {
  return Promise.all(tarefas.map((tarefa) => Promise.resolve().then(tarefa).catch(() => null)))
}

async function rodarWorkflow(nome, args, responder) {
  const chamadas = []
  const logs = []
  const agent = async (prompt, opcoes) => {
    chamadas.push({ prompt, ...opcoes })
    await esperar(ATRASO_DO_AGENTE_MS)
    return responder(prompt, opcoes)
  }
  const executar = compilarWorkflow(nome)
  const retorno = await executar(agent, pipelineFalso, parallelFalso, () => {}, (mensagem) => logs.push(mensagem), args)
  assertFasesDeclaradas(nome, chamadas)
  return { retorno, chamadas, logs }
}

function assertFasesDeclaradas(nome, chamadas) {
  const titulos = lerMeta(nome).phases.map((fase) => fase.title)
  for (const chamada of chamadas) assert.ok(titulos.includes(chamada.phase), `fase "${chamada.phase}" fora do meta de ${nome}`)
}

function porRotulo(respostas) {
  return (_prompt, { label }) => {
    if (!(label in respostas)) throw new Error(`chamada inesperada: ${label}`)
    return respostas[label]
  }
}

function devOk(extra = {}) {
  return { status: 'OK', arquivos_alterados: ['src/login.tsx'], build_ok: true, so_falta_validacao: false, comandos_para_subir: ['pnpm dev --port 5173'], resumo: 'feito', ...extra }
}

function testerCom(veredito, extra = {}) {
  return { modo: 'browser', veredito, falhas: [], evidencias: [], logs_relevantes: [], ...extra }
}

function tarefa(id, teste = 'browser') {
  return { id, briefing_dev: `implementar ${id}`, teste, briefing_tester: `validar ${id}` }
}

const FALHA_DO_LOGIN = { tipo: 'e2e', onde: '/login', viewport: 'desktop', descricao: 'botão Entrar não responde ao clique' }

async function cenarioCorrecaoAteAprovar() {
  const { retorno, chamadas } = await rodarWorkflow('executar-lote', { tarefas: [tarefa('t1')] }, porRotulo({
    't1 · dev #1': devOk(),
    't1 · tester #1': testerCom('FALHOU', { falhas: [FALHA_DO_LOGIN], recomendacao_para_dev: 'ligar o onClick do botão Entrar' }),
    't1 · dev #2': devOk(),
    't1 · tester #2': testerCom('PASSOU'),
  }))
  assert.deepEqual(chamadas.map((chamada) => chamada.label), ['t1 · dev #1', 't1 · tester #1', 't1 · dev #2', 't1 · tester #2'])
  assert.equal(retorno[0].status_final, 'PASSOU')
  assert.equal(retorno[0].tentativas, 2)
  assert.equal(retorno[0].tester.veredito, 'PASSOU')
  const [primeiroDev, primeiroTester, devDeCorrecao] = chamadas
  assert.equal(primeiroDev.agentType, 'forge:dev')
  assert.equal(primeiroTester.agentType, 'forge:tester')
  assert.ok(primeiroDev.schema && primeiroTester.schema, 'dev e tester precisam de schema')
  for (const trecho of ['validar t1', 'src/login.tsx', 'pnpm dev --port 5173']) assert.ok(primeiroTester.prompt.includes(trecho), `prompt do tester sem "${trecho}"`)
  for (const trecho of ['implementar t1', FALHA_DO_LOGIN.descricao, 'ligar o onClick do botão Entrar']) assert.ok(devDeCorrecao.prompt.includes(trecho), `correção sem "${trecho}"`)
}

async function cenarioDevParcial() {
  const parcial = devOk({ status: 'PARCIAL', so_falta_validacao: false, proximo_briefing: 'continuar pelo formulário de cadastro' })
  const { retorno, chamadas } = await rodarWorkflow('executar-lote', { tarefas: [tarefa('t2')] }, porRotulo({ 't2 · dev #1': parcial }))
  assert.equal(chamadas.length, 1, 'tester não deve rodar após dev PARCIAL')
  assert.deepEqual(retorno[0], { id: 't2', status_final: 'PARCIAL', tentativas: 1, dev: parcial, tester: null, falta_do_dev: [], proximo_briefing: 'continuar pelo formulário de cadastro' })
}

const PARCIAL_DE_VALIDACAO = { status: 'PARCIAL', so_falta_validacao: true, falta: ['ver a tela de login em desktop e mobile'] }

async function cenarioParcialDeValidacaoSegueParaTester() {
  const { retorno, chamadas, logs } = await rodarWorkflow('executar-lote', { tarefas: [tarefa('t5')] }, porRotulo({
    't5 · dev #1': devOk(PARCIAL_DE_VALIDACAO),
    't5 · tester #1': testerCom('PASSOU'),
  }))
  assert.deepEqual(chamadas.map((chamada) => chamada.label), ['t5 · dev #1', 't5 · tester #1'])
  assert.equal(retorno[0].status_final, 'PASSOU')
  assert.ok(logs.some((mensagem) => mensagem.includes('só de validação')), 'log deve registrar por que seguiu para o tester')
}

async function cenarioParcialDeValidacaoAposFalhaSegueParaTester() {
  const { retorno, chamadas } = await rodarWorkflow('executar-lote', { tarefas: [tarefa('t6')] }, porRotulo({
    't6 · dev #1': devOk(),
    't6 · tester #1': testerCom('FALHOU', { falhas: [FALHA_DO_LOGIN], recomendacao_para_dev: 'ligar o onClick' }),
    't6 · dev #2': devOk(PARCIAL_DE_VALIDACAO),
    't6 · tester #2': testerCom('PASSOU'),
  }))
  assert.equal(chamadas.length, 4)
  assert.equal(retorno[0].status_final, 'PASSOU')
  assert.equal(retorno[0].tentativas, 2)
}

async function cenarioParcialDeValidacaoSemTesteVoltaParcial() {
  const parcial = devOk({ ...PARCIAL_DE_VALIDACAO, proximo_briefing: 'só conferir a saída gerada' })
  const { retorno, chamadas } = await rodarWorkflow('executar-lote', { tarefas: [tarefa('t7', 'nenhum')] }, porRotulo({ 't7 · dev #1': parcial }))
  assert.equal(chamadas.length, 1, 'sem teste não há tester para validar')
  assert.equal(retorno[0].status_final, 'PARCIAL')
  assert.equal(retorno[0].proximo_briefing, 'só conferir a saída gerada')
}

async function cenarioParcialSemBuildOkVoltaParcial() {
  const parcial = devOk({ ...PARCIAL_DE_VALIDACAO, build_ok: false })
  const { retorno, chamadas } = await rodarWorkflow('executar-lote', { tarefas: [tarefa('t8')] }, porRotulo({ 't8 · dev #1': parcial }))
  assert.equal(chamadas.length, 1, 'build quebrado não vai para o tester')
  assert.equal(retorno[0].status_final, 'PARCIAL')
}

async function cenarioTesterRecebeOQueODevNaoVerificou() {
  const { retorno, chamadas } = await rodarWorkflow('executar-lote', { tarefas: [tarefa('t9')] }, porRotulo({
    't9 · dev #1': devOk(PARCIAL_DE_VALIDACAO),
    't9 · tester #1': testerCom('PASSOU'),
  }))
  const promptDoTester = chamadas.find((chamada) => chamada.label === 't9 · tester #1').prompt
  assert.ok(promptDoTester.includes('O dev não verificou'), 'prompt do tester sem a seção do que o dev não verificou')
  assert.ok(promptDoTester.includes(PARCIAL_DE_VALIDACAO.falta[0]), 'prompt do tester sem o texto de dev.falta')
  assert.deepEqual(retorno[0].falta_do_dev, PARCIAL_DE_VALIDACAO.falta)
}

async function cenarioPromptSemFaltaNaoTemSecao() {
  const { retorno, chamadas } = await rodarWorkflow('executar-lote', { tarefas: [tarefa('t10')] }, porRotulo({
    't10 · dev #1': devOk(),
    't10 · tester #1': testerCom('PASSOU'),
  }))
  assert.ok(!chamadas[1].prompt.includes('O dev não verificou'), 'sem dev.falta não deve haver a seção')
  assert.deepEqual(retorno[0].falta_do_dev, [])
}

async function cenarioBloqueadoDeValidacaoVoltaBloqueadoSemTester() {
  const bloqueado = devOk({ status: 'BLOQUEADO', so_falta_validacao: true, pendencias: ['falta credencial'] })
  const { retorno, chamadas } = await rodarWorkflow('executar-lote', { tarefas: [tarefa('t11')] }, porRotulo({ 't11 · dev #1': bloqueado }))
  assert.equal(chamadas.length, 1, 'dev BLOQUEADO não vai para o tester')
  assert.equal(retorno[0].status_final, 'BLOQUEADO')
}

async function cenarioParcialDeValidacaoComTesterSempreFalhando() {
  const falhou = testerCom('FALHOU', { falhas: [FALHA_DO_LOGIN], recomendacao_para_dev: 'corrigir' })
  const responder = (_prompt, { label }) => (label.includes('dev') ? devOk(PARCIAL_DE_VALIDACAO) : falhou)
  const { retorno, chamadas } = await rodarWorkflow('executar-lote', { tarefas: [tarefa('t12')], max_tentativas: 2 }, responder)
  assert.equal(chamadas.length, 4)
  assert.equal(retorno[0].status_final, 'FALHOU')
  assert.equal(retorno[0].tentativas, 2)
}

async function cenarioDevNulo() {
  const { retorno, chamadas, logs } = await rodarWorkflow('executar-lote', { tarefas: [tarefa('t3')] }, porRotulo({ 't3 · dev #1': null }))
  assert.equal(chamadas.length, 1)
  assert.equal(retorno[0].status_final, 'BLOQUEADO')
  assert.equal(retorno[0].dev, null)
  assert.ok(logs.some((mensagem) => mensagem.includes('null')), 'log deve registrar o dev sem retorno')
}

async function cenarioFalhaAposMaxTentativas() {
  const falhou = testerCom('FALHOU', { falhas: [FALHA_DO_LOGIN], recomendacao_para_dev: 'corrigir' })
  const responder = (_prompt, { label }) => (label.includes('dev') ? devOk() : falhou)
  const { retorno, chamadas } = await rodarWorkflow('executar-lote', { tarefas: [tarefa('t4')], max_tentativas: 2 }, responder)
  assert.equal(chamadas.length, 4)
  assert.equal(retorno[0].status_final, 'FALHOU')
  assert.equal(retorno[0].tentativas, 2)
}

function criarMedidorDeConcorrencia() {
  const medidor = { ativos: { browser: 0, contrato: 0 }, maximo: { browser: 0, contrato: 0 } }
  medidor.responder = async (_prompt, { label }) => {
    if (label.includes('dev')) return devOk()
    const modo = label.startsWith('b') ? 'browser' : 'contrato'
    medidor.ativos[modo] += 1
    medidor.maximo[modo] = Math.max(medidor.maximo[modo], medidor.ativos[modo])
    await esperar(DURACAO_DO_TESTER_MS)
    medidor.ativos[modo] -= 1
    return testerCom('PASSOU', { modo })
  }
  return medidor
}

async function cenarioTestersBrowserEmFila() {
  const medidor = criarMedidorDeConcorrencia()
  const tarefas = [tarefa('b1'), tarefa('b2'), tarefa('c1', 'contrato'), tarefa('c2', 'contrato')]
  const { retorno } = await rodarWorkflow('executar-lote', { tarefas }, medidor.responder)
  assert.deepEqual(retorno.map((resultado) => resultado.status_final), ['PASSOU', 'PASSOU', 'PASSOU', 'PASSOU'])
  assert.equal(medidor.maximo.browser, 1, 'dois testers browser rodaram ao mesmo tempo')
  assert.equal(medidor.maximo.contrato, 2, 'testers contrato deveriam rodar em paralelo')
}

function achado(onde) {
  return { o_que: `trecho em ${onde}`, onde, detalhe: 'linha relevante' }
}

function veredito(indice, refutado = false, motivo = 'confere') {
  return { indice, refutado, motivo, evidencia: 'trecho lido' }
}

function confirmarTodos(quantidade) {
  return { vereditos: Array.from({ length: quantidade }, (_, posicao) => veredito(posicao + 1)) }
}

function frentesDe(...titulos) {
  return titulos.map((titulo) => ({ titulo, escopo: `src/${titulo.toLowerCase()}` }))
}

// Stub por frente: a varredura devolve achados[titulo] e o verificador em lote devolve vereditos[titulo].
function responderInvestigacao({ achados, vereditos, lacunas = [] }) {
  return (_prompt, { label }) => {
    const [etapa, titulo] = label.split(' · ')
    if (etapa === 'varredura') return { status: 'OK', resposta: `resposta de ${titulo}`, achados: achados[titulo] }
    if (etapa === 'verificar') return vereditos[titulo]
    if (label === 'completude') return { lacunas }
    throw new Error(`chamada inesperada: ${label}`)
  }
}

const ACHADOS_DA_FRENTE_GRANDE = Array.from({ length: 10 }, (_, indice) => achado(`b.ts:${indice + 1}`))
const ACHADOS_DE_ROTAS = [achado('a.ts:1'), achado('a.ts:9')]

async function cenarioInvestigarComRefutacao() {
  const args = { pergunta: 'onde a sessão é validada?', frentes: frentesDe('Rotas', 'Banco') }
  const { retorno, chamadas, logs } = await rodarWorkflow('investigar', args, responderInvestigacao({
    achados: { Rotas: ACHADOS_DE_ROTAS, Banco: ACHADOS_DA_FRENTE_GRANDE },
    vereditos: { Rotas: { vereditos: [veredito(1), veredito(2, true, 'a linha 9 é um comentário')] }, Banco: confirmarTodos(8) },
    lacunas: ['falta o fluxo de logout'],
  }))
  const [rotas, banco] = retorno.frentes
  assert.deepEqual(rotas.achados_confirmados.map((item) => item.onde), ['a.ts:1'])
  assert.deepEqual(rotas.achados_refutados.map((item) => [item.onde, item.motivo_refutacao]), [['a.ts:9', 'a linha 9 é um comentário']])
  assert.equal(banco.achados_confirmados.length, 8)
  assert.deepEqual(banco.achados_nao_verificados.map((item) => item.onde), ['b.ts:9', 'b.ts:10'])
  const verificacoesDoBanco = chamadas.filter((chamada) => chamada.label === 'verificar · Banco')
  assert.equal(verificacoesDoBanco.length, 1, 'um cético por frente, não um por achado')
  assert.ok(verificacoesDoBanco[0].prompt.includes('b.ts:8') && !verificacoesDoBanco[0].prompt.includes('b.ts:9'), 'cético só recebe os achados dentro do teto')
  assert.ok(verificacoesDoBanco[0].prompt.includes('NÃO é refutado'), 'prompt do cético precisa dizer que incompletude não é refutação')
  assert.ok(logs.some((mensagem) => mensagem.includes('b.ts:9, b.ts:10')), 'log deve citar os achados fora do teto')
  assert.ok(chamadas.every((chamada) => chamada.agentType === 'forge:scout'))
  const completude = chamadas.find((chamada) => chamada.label === 'completude')
  assert.ok(completude.prompt.includes('a.ts:1') && !completude.prompt.includes('a.ts:9'), 'completude só recebe achados sobreviventes')
  assert.deepEqual(retorno.lacunas, ['falta o fluxo de logout'])
  assert.equal(retorno.pergunta, args.pergunta)
}

async function cenarioInvestigarVereditoFaltando() {
  const achados = { Rotas: [achado('a.ts:1'), achado('a.ts:5'), achado('a.ts:9')] }
  const { retorno, logs } = await rodarWorkflow('investigar', { pergunta: 'p?', frentes: frentesDe('Rotas') }, responderInvestigacao({
    achados,
    vereditos: { Rotas: { vereditos: [veredito(1), veredito(3)] } },
  }))
  const [rotas] = retorno.frentes
  assert.deepEqual(rotas.achados_confirmados.map((item) => item.onde), ['a.ts:1', 'a.ts:9'])
  assert.deepEqual(rotas.achados_nao_verificados.map((item) => item.onde), ['a.ts:5'])
  assert.ok(logs.some((mensagem) => mensagem.includes('a.ts:5') && mensagem.includes('sem veredito')), 'log deve citar o achado sem veredito')
}

async function cenarioInvestigarIndiceInvalidoIgnorado() {
  const { retorno, logs } = await rodarWorkflow('investigar', { pergunta: 'p?', frentes: frentesDe('Rotas') }, responderInvestigacao({
    achados: { Rotas: ACHADOS_DE_ROTAS },
    vereditos: { Rotas: { vereditos: [veredito(0, true, 'fora'), veredito(1), veredito(3, true, 'fora'), veredito(1, true, 'repetido')] } },
  }))
  const [rotas] = retorno.frentes
  assert.deepEqual(rotas.achados_confirmados.map((item) => item.onde), ['a.ts:1'])
  assert.deepEqual(rotas.achados_refutados, [], 'veredito fora da lista ou repetido não refuta nada')
  assert.deepEqual(rotas.achados_nao_verificados.map((item) => item.onde), ['a.ts:9'])
  assert.equal(logs.filter((mensagem) => mensagem.includes('fora da lista')).length, 2)
}

async function cenarioInvestigarVerificadorNuloEFrenteVazia() {
  const { retorno, chamadas } = await rodarWorkflow('investigar', { pergunta: 'p?', frentes: frentesDe('Rotas', 'Vazia') }, responderInvestigacao({
    achados: { Rotas: ACHADOS_DE_ROTAS, Vazia: [] },
    vereditos: { Rotas: null },
  }))
  const [rotas, vazia] = retorno.frentes
  assert.deepEqual(rotas.achados_nao_verificados.map((item) => item.onde), ['a.ts:1', 'a.ts:9'])
  assert.deepEqual(rotas.achados_confirmados, [])
  assert.deepEqual(vazia.achados_nao_verificados, [])
  assert.ok(!chamadas.some((chamada) => chamada.label === 'verificar · Vazia'), 'frente sem achados não chama o cético')
}

async function cenarioInvestigarContagemDeAgentes() {
  const cincoAchados = (prefixo) => Array.from({ length: 5 }, (_, indice) => achado(`${prefixo}.ts:${indice + 1}`))
  const { chamadas } = await rodarWorkflow('investigar', { pergunta: 'p?', frentes: frentesDe('Rotas', 'Banco') }, responderInvestigacao({
    achados: { Rotas: cincoAchados('a'), Banco: cincoAchados('b') },
    vereditos: { Rotas: confirmarTodos(5), Banco: confirmarTodos(5) },
  }))
  const rotulos = chamadas.map((chamada) => chamada.label).sort()
  assert.deepEqual(rotulos, ['completude', 'varredura · Banco', 'varredura · Rotas', 'verificar · Banco', 'verificar · Rotas'])
  const itemDoAchado = chamadas.find((chamada) => chamada.label.startsWith('varredura')).schema.properties.achados.items
  assert.equal(itemDoAchado.additionalProperties, false, 'achado do scout não aceita chave extra')
  assert.deepEqual(itemDoAchado.required, ['o_que', 'onde', 'detalhe'])
  const itemDoVeredito = chamadas.find((chamada) => chamada.label.startsWith('verificar')).schema.properties.vereditos.items
  assert.ok(itemDoVeredito.required.includes('evidencia'))
  assert.equal(itemDoVeredito.properties.evidencia.minLength, undefined, 'evidencia curta precisa passar no schema')
}

async function cenarioRegrasDoRuntime() {
  for (const nome of ['executar-lote', 'investigar']) {
    const texto = lerScript(nome)
    assert.ok(texto.startsWith('export const meta = {'), `${nome}: meta precisa ser a primeira instrução`)
    assert.equal(lerMeta(nome).name, nome)
    for (const padrao of APIS_PROIBIDAS) assert.ok(!padrao.test(texto), `${nome}: usa API proibida ${padrao}`)
  }
}

const CENARIOS = [
  ['regras do runtime: meta literal primeiro, sem APIs proibidas', cenarioRegrasDoRuntime],
  ['executar-lote: dev OK → tester FALHOU → dev OK → tester PASSOU', cenarioCorrecaoAteAprovar],
  ['executar-lote: dev PARCIAL volta para a raiz sem tester', cenarioDevParcial],
  ['executar-lote: dev PARCIAL só de validação → tester PASSOU → PASSOU', cenarioParcialDeValidacaoSegueParaTester],
  ['executar-lote: tester FALHOU → dev PARCIAL só de validação → tester PASSOU', cenarioParcialDeValidacaoAposFalhaSegueParaTester],
  ['executar-lote: dev PARCIAL só de validação com teste nenhum volta PARCIAL', cenarioParcialDeValidacaoSemTesteVoltaParcial],
  ['executar-lote: dev PARCIAL com build quebrado volta PARCIAL', cenarioParcialSemBuildOkVoltaParcial],
  ['executar-lote: tester recebe dev.falta e o resultado traz falta_do_dev', cenarioTesterRecebeOQueODevNaoVerificou],
  ['executar-lote: sem dev.falta o prompt do tester não tem a seção', cenarioPromptSemFaltaNaoTemSecao],
  ['executar-lote: dev BLOQUEADO com so_falta_validacao volta BLOQUEADO sem tester', cenarioBloqueadoDeValidacaoVoltaBloqueadoSemTester],
  ['executar-lote: PARCIAL de validação com tester sempre FALHOU → FALHOU', cenarioParcialDeValidacaoComTesterSempreFalhando],
  ['executar-lote: dev null vira BLOQUEADO', cenarioDevNulo],
  ['executar-lote: FALHOU após o máximo de tentativas', cenarioFalhaAposMaxTentativas],
  ['executar-lote: testers browser em fila, contrato em paralelo', cenarioTestersBrowserEmFila],
  ['investigar: achado refutado, teto de 8 e lacunas', cenarioInvestigarComRefutacao],
  ['investigar: achado sem veredito fica não verificado', cenarioInvestigarVereditoFaltando],
  ['investigar: veredito com índice inválido ou repetido é ignorado', cenarioInvestigarIndiceInvalidoIgnorado],
  ['investigar: verificador null e frente sem achados', cenarioInvestigarVerificadorNuloEFrenteVazia],
  ['investigar: 2 frentes com 5 achados = 5 agentes e schemas estritos', cenarioInvestigarContagemDeAgentes],
]

let quantidadeDeFalhas = 0
for (const [nome, rodar] of CENARIOS) {
  try {
    await rodar()
    console.log(`ok    ${nome}`)
  } catch (erro) {
    quantidadeDeFalhas += 1
    console.log(`FALHA ${nome}\n      ${erro.message}`)
  }
}
console.log(`\n${CENARIOS.length - quantidadeDeFalhas}/${CENARIOS.length} cenários passaram`)
process.exit(quantidadeDeFalhas > 0 ? 1 : 0)
