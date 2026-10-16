import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

function scenario(view, names) {
  const source = readFileSync(new URL(`../src/views/${view}.vue`, import.meta.url), 'utf8').match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1]
  const ast = ts.createSourceFile('view.ts', source, ts.ScriptTarget.Latest, true)
  const handlers = ast.statements.filter(ts.isFunctionDeclaration).map(n => n.getText(ast)).join('\n')
  const code = ts.transpileModule('let requestId = 0;\n' + handlers, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
  const ctx = { stage3Api: {}, sourceApi: {}, ElMessage: { success() {}, error() {} } }
  for (const name of names) ctx[name] = { value: null }
  vm.runInNewContext(code, ctx)
  return ctx
}
const discover = () => scenario('DiscoverView', ['active', 'range', 'page', 'data', 'error', 'loading', 'busy'])
test('discover network failure is distinct from empty results and retry succeeds', async () => {
  const s = discover(), old = { items: [{ id: 'old' }] }
  s.data.value = old; s.page.value = 4
  s.stage3Api.discover = async () => { throw Error('offline') }
  await s.load(true)
  assert.equal(s.page.value, 1); assert.equal(s.data.value, old)
  assert.match(s.error.value, /失败/); assert.equal(s.loading.value, false)
  s.stage3Api.discover = async () => ({ items: [], total: 0 })
  await s.load()
  assert.equal(s.error.value, ''); assert.equal(s.data.value.total, 0)
})
test('late discover response cannot overwrite the newer channel', async () => {
  const s = discover(); let release
  s.stage3Api.discover = () => new Promise(resolve => { release = resolve })
  const first = s.load()
  s.stage3Api.discover = async () => ({ items: [{ id: 'new' }] })
  await s.select('all')
  release({ items: [{ id: 'old' }] }); await first
  assert.equal(s.data.value.items[0].id, 'new')
})
test('favorite is single-flight, failure never claims success or reloads', async () => {
  const s = discover(); let reject; let writes = 0, successes = 0, errors = 0
  s.stage3Api.favorite = () => { writes++; return new Promise((_, no) => { reject = no }) }
  s.ElMessage.success = () => successes++; s.ElMessage.error = () => errors++
  const pending = s.act('one', 'favorite')
  await s.act('one', 'favorite'); reject(Error('offline')); await pending
  assert.equal(writes, 1); assert.equal(successes, 0); assert.equal(errors, 1); assert.equal(s.busy.value, null)
})
test('sources list failure preserves known source status and is retryable', async () => {
  const s = scenario('SourcesView', ['loading', 'loadError', 'sources']), old = [{ id: 'one' }]
  s.sources.value = old
  s.sourceApi.list = async () => { throw Error('offline') }
  await s.loadSources()
  assert.equal(s.sources.value, old); assert.match(s.loadError.value, /失败/)
  s.sourceApi.list = async () => []
  await s.loadSources(); assert.equal(s.loadError.value, '')
})
test('source log failure clears old records and does not masquerade as empty success', async () => {
  const s = scenario('SourcesView', ['logSource', 'logsLoading', 'runs', 'logsError'])
  s.runs.value = [{ id: 'old' }]
  s.sourceApi.runs = async () => { throw Error('offline') }
  await s.openLogs({ id: 'new' })
  assert.equal(s.runs.value.length, 0); assert.match(s.logsError.value, /失败/); assert.equal(s.logsLoading.value, false)
})
