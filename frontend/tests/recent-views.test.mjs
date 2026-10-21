import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const source = readFileSync(new URL('../src/utils/recentViews.ts', import.meta.url), 'utf8')
const ast = ts.createSourceFile('activity.ts', source, ts.ScriptTarget.Latest, true)
const declarations = ast.statements.filter(n => !ts.isImportDeclaration(n)).map(n => n.getText(ast).replace(/^export\s+/, '')).join('\n')
const code = ts.transpileModule(declarations, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText

test('browsing notifies the workspace only after persistence and failure stays recoverable', async () => {
  let release, events = 0, warnings = 0
  const ctx = { stage3Api: { recordView: () => new Promise(resolve => { release = resolve }) },
    window: { dispatchEvent: () => { events++ } }, Event: class {}, ElMessage: { warning: () => { warnings++ } } }
  vm.runInNewContext(code, ctx)
  const pending = ctx.recordRecentView('content', 'actual-id')
  assert.equal(events, 0)
  release()
  assert.equal(await pending, true)
  assert.equal(events, 1)
  ctx.stage3Api.recordView = async () => { throw Error('offline') }
  assert.equal(await ctx.recordRecentView('report', 'mine'), false)
  assert.equal(events, 1)
  assert.equal(warnings, 1)
})
