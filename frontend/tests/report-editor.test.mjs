import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const source = readFileSync(new URL('../src/views/ReportEditorView.vue', import.meta.url), 'utf8').split('<script setup lang="ts">')[1].split('</script>')[0]
const ast = ts.createSourceFile('editor.ts', source, ts.ScriptTarget.Latest, true)
const code = ts.transpileModule(ast.statements.filter(n => !ts.isImportDeclaration(n)).map(n => n.getText(ast)).join('\n'), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
function setup(api) {
  let leave
  const ctx = { ref: value => ({ value }), computed: fn => ({ get value() { return fn() } }),
    useRoute: () => ({ params: { id: 'mine' } }), useRouter: () => ({}),
    reportsApi: api, watch() {}, onMounted() {}, onBeforeUnmount() {}, onBeforeRouteLeave: fn => { leave = fn },
    ElMessage: { success() {}, error() {}, warning() {} }, setTimeout, clearTimeout }
  vm.runInNewContext(code + `\nObject.assign(globalThis,{content,savedContent,dirty,report,exportJob})`, ctx)
  ctx.report.value = { current_version: { content_markdown: '', citations: [] } }
  return { ctx, leave: () => leave() }
}
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b }); return {promise,resolve,reject} }
test('saves snapshots and drains edits arriving during save and version refresh before export', async () => {
  const first=deferred(), refresh=deferred(), received=[]; let lists=0, exported
  const {ctx}=setup({saveVersion: async (_, data) => { received.push(data.content_markdown); if(received.length===1) await first.promise; return {id:String(received.length),version_number:received.length,citations:[]} },
    versions: async () => { if(++lists===1) await refresh.promise; return [] },
    export: async () => {exported=received.at(-1);return {status:'failed'} }})
  ctx.content.value='A'; const saving=ctx.save(true); ctx.content.value='B'; const exporting=ctx.startExport('pdf')
  first.resolve(); await new Promise(resolve=>setImmediate(resolve))
  assert.deepEqual(received,['A','B']); assert.equal(exported,undefined)
  ctx.content.value='C'; refresh.resolve(); await Promise.all([saving,exporting])
  assert.deepEqual(received,['A','B','C']); assert.equal(exported,'C'); assert.equal(ctx.dirty.value,false)
})
test('failed saves retain dirty content, block leaving, and can be retried', async () => {
  let fails=true
  const {ctx,leave}=setup({saveVersion: async()=>{if(fails)throw Error('offline');return {id:'v',version_number:1,citations:[]}},versions:async()=>[]})
  ctx.content.value='keep me';assert.equal(await leave(),false);assert.equal(ctx.dirty.value,true)
  fails=false;assert.equal(await leave(),true);assert.equal(ctx.savedContent.value,'keep me')
})
test('download uses authenticated blob response and releases object URL', async () => {
  const calls=[];const {ctx}=setup({download:async id=>{calls.push(id);return {data:'blob'}}})
  ctx.URL={createObjectURL:blob=>{assert.equal(blob,'blob');return 'blob:mine'},revokeObjectURL:url=>calls.push(url)}
  ctx.document={createElement:()=>({click(){calls.push(this.href,this.download)},remove(){}}),body:{appendChild(){}}}
  ctx.setTimeout=fn=>fn();ctx.exportJob.value={format:'pdf'};await ctx.download('owned')
  assert.deepEqual(calls,['owned','blob:mine','report.pdf','blob:mine'])
})


test('rewrite response cannot replace edits made while the model request is pending', async () => {
  const response=deferred(); const {ctx}=setup({rewrite:async()=>response.promise})
  ctx.document={querySelector:()=>({selectionStart:0,selectionEnd:3})};ctx.content.value='old text'
  const pending=ctx.rewrite('shorten');ctx.content.value='new text';response.resolve({text:'model'})
  await pending;assert.equal(ctx.content.value,'new text')
})
