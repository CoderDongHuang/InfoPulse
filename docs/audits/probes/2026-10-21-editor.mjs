// Extract and execute the actual Vue save handler with a deferred network reply.
import { readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const require = createRequire(new URL('../../../frontend/package.json', import.meta.url))
const ts = require('typescript')
const vue = readFileSync(new URL('../../../frontend/src/views/ReportEditorView.vue', import.meta.url), 'utf8')
const script = vue.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1]
const ast = ts.createSourceFile('editor.ts', script, ts.ScriptTarget.Latest, true)
const handler = ast.statements.find(n => ts.isFunctionDeclaration(n) && n.name.text === 'save')
const code = ts.transpileModule(handler.getText(ast), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
let resolveSave, serverContent
const ctx = {
  id: 'audit', content: { value: 'A' }, savedContent: { value: 'initial' }, saving: { value: false }, versions: { value: [] },
  report: { value: { current_version: { structured_content: {}, citations: [] } } },
  ElMessage: { success() {} },
  reportsApi: {
    saveVersion(_id, payload) { serverContent = payload.content_markdown; return new Promise(resolve => { resolveSave = resolve }) },
    async versions() { return [] },
  },
}
ctx.dirty = { get value() { return ctx.content.value !== ctx.savedContent.value } }
vm.runInNewContext(code, ctx)
const inflight = ctx.save(true)
ctx.content.value = 'B'
resolveSave({ id: 'v1', version_number: 1, citations: [] })
await inflight
assert.equal(serverContent, 'A')
assert.equal(ctx.savedContent.value, 'B')
assert.equal(ctx.dirty.value, false)
const result = JSON.stringify({ serverContent, editorContent: ctx.content.value, markedSaved: ctx.savedContent.value, dirty: ctx.dirty.value }, null, 2)
writeFileSync(new URL('./2026-10-21-editor.results.json', import.meta.url), result + '\n')
console.log(result)
