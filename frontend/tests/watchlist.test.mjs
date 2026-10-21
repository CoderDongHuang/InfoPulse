import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import * as vue from 'vue'
import * as pinia from 'pinia'

const source = readFileSync(new URL('../src/stores/watchlist.ts', import.meta.url), 'utf8')
const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText
const topic = (name, id = name) => ({ id, name, keywords: [], enabled: true, created_at: '2026-10-20T00:00:00Z' })
function deferred() { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
function scenario(api = {}, legacy = []) {
  const user = vue.reactive({ userInfo: { id: 'alice' } })
  const storage = new Map([['infopulse.watchlist.v1', JSON.stringify(legacy)]])
  const exports = {}
  const ctx = { exports, localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) },
    require: name => ({ vue, pinia, '@/api/stage3': { stage3Api: api }, '@/stores/user': { useUserStore: () => user } })[name] }
  vm.runInNewContext(code, ctx)
  const store = exports.useWatchlistStore(pinia.createPinia())
  return { store, user, storage, api, remaining: () => JSON.parse(storage.get('infopulse.watchlist.v1')) }
}

test('follows persist through API; failed unfollow keeps the record', async () => {
  let removed
  const s = scenario({ topics: async () => [topic('AI')], addTopic: async name => topic(name), removeTopic: async id => { removed = id; throw Error('offline') } })
  await s.store.load()
  await s.store.toggle({ title: 'Java' })
  assert.equal(s.store.has('Java'), true)
  await assert.rejects(s.store.remove('AI'), /offline/)
  assert.equal(removed, 'AI')
  assert.equal(s.store.has('AI'), true)
  assert.match(s.store.error, /记录已保留/)
})

test('failed read retains existing data and exposes retry state', async () => {
  const s = scenario({ topics: async () => [topic('AI')] })
  await s.store.load()
  s.api.topics = async () => { throw Error('offline') }
  await assert.rejects(s.store.load(), /offline/)
  assert.equal(s.store.has('AI'), true)
  assert.match(s.store.error, /加载失败/)
  assert.equal(s.store.loading, false)
})

test('account switch discards a late read without exposing previous follows', async () => {
  const pending = deferred()
  const s = scenario({ topics: () => pending.promise })
  const loading = s.store.load()
  s.user.userInfo = { id: 'bob' }
  pending.resolve([topic('Alice private')])
  await assert.rejects(loading, /账号已变化/)
  assert.equal(s.store.count, 0)
  assert.equal(s.store.error, '')
})

test('late write cannot repopulate another account', async () => {
  const pending = deferred()
  const s = scenario({ addTopic: () => pending.promise })
  const saving = s.store.add({ title: 'Alice topic' })
  s.user.userInfo = { id: 'bob' }
  pending.resolve(topic('Alice topic'))
  await assert.rejects(saving, /账号已变化/)
  assert.equal(s.store.count, 0)
  assert.equal(s.store.busy, false)
})

test('older read cannot overwrite a successful follow and writes are single-flight', async () => {
  const read = deferred(), write = deferred()
  let writes = 0, reads = 0
  const s = scenario({ topics: () => { reads++; return read.promise }, addTopic: () => { writes++; return write.promise } })
  const loading = s.store.load()
  const saving = s.store.add({ title: 'AI' })
  assert.equal(await s.store.add({ title: 'Java' }), false)
  await s.store.load()
  assert.equal(reads, 1)
  write.resolve(topic('AI')); await saving
  read.resolve([]); await loading
  assert.equal(writes, 1)
  assert.equal(s.store.has('AI'), true)
  assert.equal(s.store.loading, false)
})

test('legacy import is explicit; partial failure preserves unimported records', async () => {
  const s = scenario({ topics: async () => [], addTopic: async name => { if (name === 'Java') throw Error('offline'); return topic(name) } }, [{ title: 'AI' }, { title: 'Java', sourceUrl: 'https://example.com/java' }])
  await s.store.load()
  assert.equal(s.store.count, 0)
  assert.equal(s.remaining().length, 2)
  await assert.rejects(s.store.importLegacy(), /offline/)
  assert.equal(s.store.has('AI'), true)
  assert.deepEqual(s.remaining(), [{ title: 'Java', sourceUrl: 'https://example.com/java' }])
  assert.equal(s.store.importing, false)
  s.api.topics = async () => [topic('AI')]
  s.api.addTopic = async name => topic(name)
  await s.store.importLegacy()
  assert.equal(s.store.count, 2)
  assert.deepEqual(s.remaining(), [])
})

test('overlong legacy title remains intact and does not submit an invalid request', async () => {
  const title = '长'.repeat(121)
  const s = scenario({ topics: async () => [], addTopic: () => assert.fail('must not submit') }, [{ title }])
  await assert.rejects(s.store.importLegacy(), /120/)
  assert.equal(s.remaining()[0].title, title)
  assert.equal(s.store.importing, false)
})
