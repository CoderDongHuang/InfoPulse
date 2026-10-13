import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const compile = source => ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText
const dialog = compile(readFileSync(new URL('../src/utils/dialog.ts', import.meta.url), 'utf8'))
const nodes = [
  { id: 'a', name: 'Source', evidence_content_ids: ['evidence'] },
  { id: 'b', name: 'Target', evidence_content_ids: ['evidence'] },
]
const cases = [
  ['History', 'remove', ['selected'], ['deleteHistory', 'selected'], ['confirm']],
  ['Subscriptions', 'remove', [{ id: 'selected', name: 'Subscription' }], ['deleteSubscription', 'selected'], ['confirm']],
  ['Multimodal', 'remove', ['selected'], ['remove', 'selected'], ['confirm']],
  ['Knowledge', 'createBase', [], ['create', { name: 'Knowledge', description: '' }], ['Knowledge']],
  ['Knowledge', 'deleteBase', [], ['remove', 'selected'], ['Knowledge']],
  ['Knowledge', 'importWeb', [], ['importWeb', 'selected', 'https://example.org'], ['https://example.org']],
  ['Knowledge', 'removeDoc', [{ id: 'selected' }], ['removeDocument', 'selected'], ['confirm']],
  ['Alerts', 'act', ['resolve'], ['act', 'selected', { action: 'resolve', note: '', assignee_id: null }], ['']],
  ['Alerts', 'remove', [{ id: 'selected', name: 'Rule' }], ['removeRule', 'selected'], ['confirm']],
  ['Graph', 'addEntity', [], ['addEntity', 'event', {
    name: 'Name', entity_type: 'organization', aliases: ['Alias', 'Other'], role: 'mentioned', evidence_content_ids: [],
  }], ['Name', 'organization', ' Alias，Other, ']],
  ['Graph', 'merge', [], ['mergeEntity', 'event', { source_entity_id: 'a', target_entity_id: 'b' }], ['Source', 'Target']],
  ['Graph', 'addRelation', [], ['addRelation', 'event', {
    from_entity_id: 'a', to_entity_id: 'b', relation_type: 'related', evidence_content_ids: ['evidence'], confidence: 1,
  }], ['Source', 'Target', 'related']],
]

function scenario(view, handlerName, answers, failureAt = -1, failure = 'cancel', apiError) {
  const source = readFileSync(new URL(`../src/views/${view}View.vue`, import.meta.url), 'utf8')
    .match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1]
  const ast = ts.createSourceFile('view.ts', source, ts.ScriptTarget.Latest, true)
  const handler = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === handlerName)
  assert.ok(handler, `${view}.${handlerName} missing`)
  const calls = []
  let opened = 0
  const open = async prompt => {
    const step = opened++
    if (step === failureAt) throw failure
    assert.ok(step < answers.length, 'unexpected extra dialog')
    return prompt ? { value: answers[step] } : answers[step]
  }
  const api = new Proxy({}, { get: (_, method) => async (...args) => {
    calls.push([method, ...args])
    if (apiError) throw apiError
  } })
  const context = {
    exports: {}, id: 'event', graph: { value: structuredClone({ nodes }) },
    active: { value: { name: 'Knowledge' } }, activeId: { value: 'selected' },
    selected: { value: { id: 'selected' } }, busy: { value: false },
    items: { value: [{ id: 'selected' }, { id: 'keep' }] },
    ElMessageBox: { confirm: () => open(false), prompt: () => open(true) },
    ElMessage: { error: message => calls.push(['error', message]) },
    workflowApi: api, automationApi: api, knowledgeApi: api, stage10Api: api, graphApi: api, api,
    load: async () => calls.push(['load']), loadDocs: async () => calls.push(['loadDocs']),
    loadBases: async () => calls.push(['loadBases']),
  }
  vm.runInNewContext(dialog, context)
  context.runDialog = context.exports.runDialog
  vm.runInNewContext(compile(handler.getText(ast)), context)
  // Normalize VM realm prototypes before assertions, while retaining actual values.
  return { context, execute: (...args) => context[handlerName](...args),
    calls: () => JSON.parse(JSON.stringify(calls)), opened: () => opened }
}

for (const [view, handler, args, expected, answers] of cases) {
  test(`${view}.${handler}: cancel/close at every step preserve data; confirmation writes once; failures propagate`, async () => {
    for (const action of ['cancel', 'close']) {
      for (let step = 0; step < answers.length; step++) {
        const result = scenario(view, handler, answers, step, action)
        await result.execute(...args)
        assert.deepEqual(result.calls(), [], `${action} at step ${step} caused side effects`)
        assert.equal(result.opened(), step + 1, 'continued asking after dismissal')
        assert.equal(result.context.activeId.value, 'selected')
        assert.equal(result.context.selected.value.id, 'selected')
        assert.equal(result.context.items.value.length, 2)
        assert.equal(result.context.busy.value, false)
      }
    }
    const success = scenario(view, handler, answers)
    await success.execute(...args)
    assert.deepEqual(success.calls()[0], expected)
    assert.equal(success.calls().filter(call => call[0] === expected[0]).length, 1)
    assert.equal(success.opened(), answers.length)
    if (view === 'History') assert.deepEqual(success.context.items.value.map(x => x.id), ['keep'])
    if (view === 'Multimodal') assert.equal(success.context.selected.value, null)
    if (handler === 'deleteBase') assert.equal(success.context.activeId.value, '')
    const error = new Error('real failure')
    const failedDialog = scenario(view, handler, answers, answers.length - 1, error)
    await assert.rejects(failedDialog.execute(...args), e => e === error)
    assert.deepEqual(failedDialog.calls(), [])
    const failedApi = scenario(view, handler, answers, -1, undefined, error)
    await assert.rejects(failedApi.execute(...args), e => e === error)
    assert.deepEqual(failedApi.calls(), [expected], 'failed write triggered refresh or success')
    assert.equal(failedApi.context.busy.value, false, 'busy state leaked')
  })
}

test('graph relation still refuses a write without event evidence', async () => {
  const result = scenario('Graph', 'addRelation', ['Source', 'Target', 'related'])
  result.context.graph.value.nodes.forEach(node => { node.evidence_content_ids = [] })
  await result.execute()
  assert.deepEqual(result.calls(), [['error', '实体没有当前事件证据，拒绝创建关系']])
})
