import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import * as vue from 'vue'

const source = readFileSync(new URL('../src/composables/useAgentView.ts', import.meta.url), 'utf8')
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
function setup() {
  const hooks = {}, locations = [], focused = []
  const route = { query: { event_id: 'stale-event', filter: 'preserved' } }
  const chat = { conversations: [{ id: 'one', title: 'First' }], active: null, tools: [], prompt: '',
    create: async () => { chat.active = { id: 'new', event_id: null, messages: [] }; return true },
    open: async id => { chat.active = { id, event_id: 'current-event', messages: [] }; return true },
    dispose: () => { hooks.disposed = true }, loadList: async () => { hooks.list = true }, loadKnowledge: async () => { hooks.knowledge = true } }
  const context = { exports: {}, require: name => {
    if (name === 'vue') return { ...vue, watch() {}, onMounted: fn => { hooks.mount = fn }, onBeforeUnmount: fn => { hooks.unmount = fn } }
    if (name === 'vue-router') return { useRoute: () => route, useRouter: () => ({ replace: async value => locations.push(value) }) }
    if (name.endsWith('useAgentChat')) return { useAgentChat: () => chat, conversationEventId: (active, fallback) => active ? active.event_id : fallback }
    return {}
  } }
  vm.runInNewContext(code, context)
  const view = context.exports.useAgentView()
  view.inputEl.value = { focus: () => focused.push('input'), style: {}, scrollHeight: 220 }
  view.historyToggle.value = { focus: () => focused.push('toggle') }
  return { view, hooks, locations, focused }
}

test('new ordinary conversation removes stale event URL and focuses composer', async () => {
  const { view, locations, focused } = setup()
  await view.create()
  assert.equal(locations[0].query.conversation, 'new')
  assert.equal(locations[0].query.event_id, undefined)
  assert.equal(locations[0].query.filter, 'preserved')
  assert.deepEqual(focused, ['input'])
})

test('opening a conversation syncs its event; closing sidebar restores keyboard focus', async () => {
  const { view, locations, focused } = setup()
  view.sidebarOpen.value = true
  await view.open('existing')
  assert.equal(locations[0].query.event_id, 'current-event')
  assert.equal(view.sidebarOpen.value, false)
  await view.closeSidebar()
  assert.deepEqual(focused, ['toggle'])
  view.historySearch.value = 'FIRST'
  assert.equal(view.visibleHistory.value.length, 1)
})

test('mount loads history and knowledge, sizes DOM input, and unmount disposes stream', async () => {
  const { view, hooks } = setup()
  await hooks.mount()
  assert.equal(hooks.list, true); assert.equal(hooks.knowledge, true)
  assert.equal(view.inputEl.value.style.height, '180px')
  hooks.unmount()
  assert.equal(hooks.disposed, true)
})
