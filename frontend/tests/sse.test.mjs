import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const source = ts.transpileModule(readFileSync(new URL('../src/utils/sse.ts', import.meta.url), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText

async function scenario(fetchImpl, kind = 'error') {
  let clock = 0, tick, cleared = 0
  const events = [], exports = {}
  const context = { exports, AbortController, TextDecoder, Date: { now: () => clock }, fetch: fetchImpl,
    window: { setInterval: fn => { tick = fn; return 1 }, clearInterval: () => cleared++ } }
  vm.runInNewContext(source, context)
  const connection = exports.createSSEConnection('/stream', { callbacks: {
    onResult: () => events.push('result'), onError: () => events.push('error'), onTimeout: () => events.push('timeout'),
  } })
  await new Promise(resolve => setImmediate(resolve))
  clock = 80000; tick(); tick(); connection.close()
  assert.deepEqual(events, [kind]); assert.equal(cleared, 1)
}

test('result and EOF clear the timer once', () => scenario(async () => new Response('event: result\r\ndata: {"ok":true}\r\n\r\n'), 'result'))
test('401 clears the timer without later timeouts', () => scenario(async () => new Response('{}', { status: 401 })))
test('network failure is terminal', () => scenario(async () => { throw new Error('offline') }))
test('premature EOF is an error', () => scenario(async () => new Response('event: progress\ndata: {}\n\n')))
test('timeout fires only once', () => scenario(() => new Promise(() => {}), 'timeout'))
