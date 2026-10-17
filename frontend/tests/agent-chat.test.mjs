import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import * as vue from 'vue'

const source = readFileSync(new URL('../src/composables/useAgentChat.ts', import.meta.url), 'utf8')
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
const context = { exports: {}, URL, require: name => name === 'vue' ? vue : {} }
vm.runInNewContext(code, context)
const { useAgentChat, citationLink, shouldSendMessage } = context.exports
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function setup(overrides = {}) {
  const calls = { create: 0, close: 0, sends: [] }
  const api = {
    list: async () => [], create: async () => { calls.create++; return { id: 'one' } },
    detail: async id => ({ id, messages: [] }), remove: async () => {},
    send: (id, body, callback) => { calls.sends.push({ id, body, callback }); return { close: () => calls.close++ } }, ...overrides,
  }
  const chat = useAgentChat(api, { bases: async () => [] })
  return { chat, calls }
}
test('Enter sends, while Shift+Enter and Chinese IME confirmation do not', () => {
  const key = { key: 'Enter', shiftKey: false, isComposing: false, keyCode: 13 }
  assert.equal(shouldSendMessage(key), true)
  for (const change of [{ shiftKey: true }, { isComposing: true }, { keyCode: 229 }, { key: 'a' }]) assert.equal(shouldSendMessage({ ...key, ...change }), false)
})
test('citation links allow only safe absolute HTTP(S) URLs without credentials', () => {
  assert.equal(citationLink('https://example.com/a'), 'https://example.com/a')
  for (const value of ['javascript:alert(1)', 'data:text/html,test', '/relative', 'https://user:pass@example.com', undefined]) assert.equal(citationLink(value), undefined)
})
test('first send creates once, blocks duplicate sends, and keeps selected contexts', async () => {
  const gate = deferred(); const { chat, calls } = setup({ create: async () => { calls.create++; await gate.promise; return { id: 'one' } } })
  chat.prompt.value = '  question  '; chat.useFavorites.value = true; chat.selectedKnowledge.value = ['kb']
  const first = chat.send(); await chat.send(); assert.equal(calls.create, 1)
  gate.resolve(); await first; await chat.send()
  assert.equal(calls.sends.length, 1)
  assert.equal(calls.sends[0].body.content, 'question')
  assert.equal(calls.sends[0].body.context_additions[0].type, 'favorite')
  assert.equal(calls.sends[0].body.knowledge_base_ids[0], 'kb')
  assert.equal(chat.canSend.value, false)
})
test('completion persists visible answer and citations and releases composer', async () => {
  const { chat, calls } = setup(); chat.prompt.value = 'q'; await chat.send()
  const emit = calls.sends[0].callback
  emit('tool.started', { name: 'search' }); emit('tool.completed', { name: 'search', count: 2 })
  emit('message.delta', { text: 'partial' }); assert.equal(chat.draft.value, 'partial')
  emit('message.completed', { id: 'answer', role: 'assistant', content: 'final', citations: [{ id: 'source' }] })
  emit('message.delta', { text: 'late' })
  assert.equal(chat.active.value.messages.length, 2)
  assert.equal(chat.active.value.messages[1].citations[0].id, 'source')
  assert.equal(chat.streaming.value, false); assert.equal(chat.draft.value, '')
  assert.equal(chat.tools.value[0].count, 2)
})
for (const type of ['error', 'message.failed']) test(`${type} restores input without inventing a completed answer`, async () => {
  const { chat, calls } = setup(); chat.prompt.value = 'recover me'; await chat.send()
  calls.sends[0].callback(type, { message: 'offline' })
  calls.sends[0].callback('message.completed', { role: 'assistant', content: 'late' })
  assert.equal(chat.streaming.value, false); assert.equal(chat.prompt.value, 'recover me'); assert.equal(chat.canSend.value, true)
  assert.equal(chat.streamError.value, 'offline'); assert.equal(chat.active.value.messages.length, 1)
})
test('synchronous send failure is recoverable', async () => {
  const { chat } = setup({ send: () => { throw Error('offline') } }); chat.prompt.value = 'q'; await chat.send()
  assert.equal(chat.streaming.value, false); assert.equal(chat.prompt.value, 'q'); assert.ok(chat.streamError.value)
})
test('switching conversation closes stream and ignores its late terminal event', async () => {
  const { chat, calls } = setup(); chat.prompt.value = 'q'; await chat.send(); await chat.open('two')
  calls.sends[0].callback('message.completed', { role: 'assistant', content: 'wrong conversation' })
  assert.equal(calls.close, 1); assert.equal(chat.active.value.id, 'two'); assert.equal(chat.active.value.messages.length, 0)
})
test('out-of-order detail responses never replace the latest selection', async () => {
  const gate = deferred(); const { chat } = setup({ detail: async id => id === 'slow' ? gate.promise : { id, messages: [] } })
  const slow = chat.open('slow'); await chat.open('fast'); gate.resolve({ id: 'slow', messages: [] }); await slow
  assert.equal(chat.active.value.id, 'fast'); assert.equal(chat.busy.value, false)
})
test('stop keeps a clearly incomplete draft and dispose invalidates callbacks', async () => {
  const { chat, calls } = setup(); chat.prompt.value = 'q'; await chat.send(); calls.sends[0].callback('message.delta', { text: 'partial' })
  chat.stop(); calls.sends[0].callback('message.delta', { text: 'late' })
  assert.equal(chat.draft.value, 'partial'); assert.equal(chat.stopped.value, true); assert.equal(chat.streaming.value, false)
  chat.dispose(); calls.sends[0].callback('message.completed', { role: 'assistant' }); assert.equal(chat.active.value.messages.length, 1)
})
test('knowledge failure does not prevent public chat or history loading', async () => {
  const chat = useAgentChat({ list: async () => [{ id: 'one' }] }, { bases: async () => { throw Error('offline') } })
  await Promise.all([chat.loadList(), chat.loadKnowledge()]); assert.equal(chat.conversations.value.length, 1); assert.ok(chat.knowledgeError.value)
})
test('create and delete failure preserve user data', async () => {
  const { chat } = setup({ create: async () => { throw Error('offline') }, remove: async () => { throw Error('offline') } })
  chat.prompt.value = 'keep'; await chat.send(); assert.equal(chat.prompt.value, 'keep'); assert.equal(chat.active.value, null)
  await chat.open('one'); chat.conversations.value = [{ id: 'one' }]; await chat.remove('one')
  assert.equal(chat.active.value.id, 'one'); assert.equal(chat.conversations.value.length, 1); assert.ok(chat.error.value)
})
test('first question becomes the new conversation title, and disposal releases pending navigation', async () => {
  let title
  const gate = deferred()
  const { chat } = setup({ create: async data => { title = data.title; return { id: 'one' } }, detail: async () => gate.promise })
  chat.prompt.value = 'A meaningful first question'; await chat.send(); assert.equal(title, 'A meaningful first question')
  const opening = chat.open('two'); assert.equal(chat.busy.value, true); chat.dispose()
  gate.resolve({ id: 'two', messages: [] }); await opening
  assert.equal(chat.busy.value, false); assert.equal(chat.active.value.id, 'one')
})
