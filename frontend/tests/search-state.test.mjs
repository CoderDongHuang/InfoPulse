import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const source = readFileSync(new URL('../src/views/SearchView.vue', import.meta.url), 'utf8').match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1]
const ast = ts.createSourceFile('search.ts', source, ts.ScriptTarget.Latest, true)
const handlers = ast.statements.filter(node => ts.isFunctionDeclaration(node)).map(node => node.getText(ast)).join('\n')
const code = ts.transpileModule(handlers, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
function scenario() {
  const ctx = { filters: {}, intelligenceApi: {}, sourceApi: {} }
  for (const key of ['query', 'page', 'loading', 'items', 'total', 'searchError', 'metadataError', 'sources', 'saved']) ctx[key] = { value: null }
  vm.runInNewContext(code, ctx)
  return ctx
}

test('search failure is explicit, preserves data, clears loading and can retry', async () => {
  const s = scenario()
  const old = [{ id: 'existing' }]
  s.items.value = old
  s.intelligenceApi.search = async () => { throw Error('offline') }
  await s.search(true)
  assert.equal(s.page.value, 1)
  assert.equal(s.loading.value, false)
  assert.equal(s.items.value, old)
  assert.match(s.searchError.value, /搜索失败/)
  const latest = [{ id: 'new' }]
  s.intelligenceApi.search = async () => ({ items: latest, total: 1 })
  await s.search()
  assert.equal(s.searchError.value, '')
  assert.equal(s.items.value, latest)
  assert.equal(s.total.value, 1)
})

test('metadata partial failure retains successful read and is independently retryable', async () => {
  const s = scenario()
  const saved = [{ id: 'saved' }]
  s.sourceApi.list = async () => { throw Error('offline') }
  s.intelligenceApi.savedSearches = async () => saved
  await s.loadMetadata()
  assert.equal(s.saved.value, saved)
  assert.match(s.metadataError.value, /仍可继续搜索/)
  const sources = [{ id: 'source' }]
  s.sourceApi.list = async () => sources
  await s.loadMetadata()
  assert.equal(s.metadataError.value, '')
  assert.equal(s.sources.value, sources)
})
