import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

// Execute the actual handler extracted with the TS parser, with boundary mocks.
const vue = readFileSync(new URL('../src/views/ReportsView.vue', import.meta.url), 'utf8')
const script = vue.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1]
const ast = ts.createSourceFile('report.ts', script, ts.ScriptTarget.Latest, true)
const handler = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'remove')
assert.ok(handler, 'report delete handler missing')
const compiled = ts.transpileModule(handler.getText(ast), {
  compilerOptions: { target: ts.ScriptTarget.ES2022 },
}).outputText

function scenario(confirm, deleteReport = async () => {}) {
  const calls = []
  const context = {
    ElMessageBox: { confirm },
    reportsApi: { remove: async id => { calls.push(['delete', id]); await deleteReport() } },
    ElMessage: { success: () => calls.push(['success']) },
    load: async () => calls.push(['reload']),
  }
  vm.runInNewContext(compiled, context)
  return { calls, execute: () => context.remove({ id: 'owned-report', title: 'Fixture' }) }
}

test('cancel and close are normal exits with no delete or reload', async () => {
  for (const action of ['cancel', 'close']) {
    const result = scenario(async () => { throw action })
    await result.execute()
    assert.deepEqual(result.calls, [])
  }
})

test('confirmation deletes exactly the selected report then refreshes', async () => {
  const result = scenario(async () => 'confirm')
  await result.execute()
  assert.deepEqual(result.calls, [['delete', 'owned-report'], ['success'], ['reload']])
})

test('unexpected confirmation and API failures are not swallowed or reported as success', async () => {
  const error = new Error('unexpected failure')
  const failedConfirmation = scenario(async () => { throw error })
  await assert.rejects(failedConfirmation.execute(), value => value === error)
  assert.deepEqual(failedConfirmation.calls, [])
  const failedDelete = scenario(async () => 'confirm', async () => { throw error })
  await assert.rejects(failedDelete.execute(), value => value === error)
  assert.deepEqual(failedDelete.calls, [['delete', 'owned-report']])
})
