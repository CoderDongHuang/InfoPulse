import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const vue = readFileSync(new URL('../src/views/HomeView.vue', import.meta.url), 'utf8')
const script = vue.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1]
const ast = ts.createSourceFile('workspace.ts', script, ts.ScriptTarget.Latest, true)
const handlers = ast.statements.filter(node => ts.isFunctionDeclaration(node)).map(node => node.getText(ast)).join('\n')
const code = ts.transpileModule(handlers, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
function scenario(api = {}) {
  const ctx = { stage3Api: api }
  for (const key of ['loading', 'error', 'data', 'pending', 'actionError', 'actionNotice', 'reloadRequested']) ctx[key] = { value: null }
  vm.runInNewContext(code, ctx)
  return ctx
}

test('workspace failure is recoverable and does not invent empty success', async () => {
  const s = scenario({ workspace: async () => { throw Error('offline') } })
  await s.load()
  assert.match(s.error.value, /加载失败/)
  assert.equal(s.data.value, null)
  assert.equal(s.loading.value, false)
  const fixture = { recent_reports: [{ id: 'mine', title: 'Real' }] }
  s.stage3Api.workspace = async () => fixture
  await s.load()
  assert.equal(s.error.value, '')
  assert.equal(s.data.value, fixture)
})

test('favorite is single-flight and refreshes only after successful write', async () => {
  let release, writes = 0, reads = 0
  const s = scenario({ favorite: () => { writes++; return new Promise(resolve => { release = resolve }) }, workspace: async () => { reads++; return {} } })
  const first = s.act('one', 'favorite')
  await s.act('two', 'favorite')
  assert.equal(writes, 1)
  assert.equal(reads, 0)
  release()
  await first
  assert.equal(reads, 1)
  assert.equal(s.pending.value, null)
  assert.equal(s.actionNotice.value, '已收藏')
})

test('feedback failure leaves data intact and never signals success', async () => {
  const s = scenario({ feedback: async () => { throw Error('denied') }, workspace: async () => { assert.fail('must not refresh') } })
  const old = { recommendations: [{ id: 'one' }] }
  s.data.value = old
  await s.act('one', 'ignore')
  assert.equal(s.data.value, old)
  assert.equal(s.actionNotice.value, '')
  assert.match(s.actionError.value, /操作失败/)
  assert.equal(s.pending.value, null)
})

test('successful feedback followed by failed reload is distinguished from failed write', async () => {
  const s = scenario({ feedback: async () => {}, workspace: async () => { throw Error('timeout') } })
  await s.act('one', 'ignore')
  assert.equal(s.actionNotice.value, '已记录反馈')
  assert.equal(s.actionError.value, '')
  assert.match(s.error.value, /加载失败/)
  assert.equal(s.pending.value, null)
})

test('a browsing update during workspace loading triggers a fresh read instead of being lost', async () => {
  let release, reads = 0
  const s = scenario({ workspace: async () => {
    reads++
    if (reads === 1) return new Promise(resolve => { release = resolve })
    return { recent_views: [{ title: 'Just read' }] }
  } })
  s.document = { visibilityState: 'visible' }
  const first = s.load()
  s.refreshVisible()
  release({ recent_views: [] })
  await first
  assert.equal(reads, 2)
  assert.equal(s.data.value.recent_views[0].title, 'Just read')
  s.document.visibilityState = 'hidden'
  s.refreshVisible()
  assert.equal(reads, 2)
})
