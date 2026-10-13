import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const plugin = readFileSync(new URL('../src/plugins/element.ts', import.meta.url), 'utf8')
const element = new Proxy({ ElLoading: { directive: { fixture: true } } }, {
  get: (target, name) => target[name] || { name },
})
const exports = {}, registered = new Map(), directives = new Map()
vm.runInNewContext(ts.transpileModule(plugin, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, {
  exports, require: name => name === 'element-plus' ? element : {},
})
exports.installElement({
  component: (name, value) => registered.set(name, value),
  directive: (name, value) => directives.set(name, value),
})

test('all current Element template tags are registered, with per-component styles', () => {
  const root = new URL('../src/', import.meta.url)
  const files = readdirSync(root, { recursive: true }).filter(file => file.endsWith('.vue'))
  const used = new Set()
  for (const file of files) {
    const source = readFileSync(new URL(file.replaceAll('\\', '/'), root), 'utf8')
    for (const match of source.matchAll(/<((?:el-[a-z-]+)|(?:El[A-Z]\w*))(?=[\s/>])/g)) {
      const name = match[1].startsWith('el-')
        ? match[1].split('-').map(word => word[0].toUpperCase() + word.slice(1)).join('')
        : match[1]
      used.add(name)
      assert.ok(registered.has(name), file + ': missing component ' + name)
    }
  }
  assert.ok(used.size > 0, 'no template components inspected')
  for (const name of used) {
    const style = name.slice(2).replace(/[A-Z]/g, (letter, index) => (index ? '-' : '') + letter.toLowerCase())
    assert.ok(plugin.includes('components/' + style + '/style/css'), 'missing style: ' + name)
  }
})

test('loading directive and programmatic message styles remain available', () => {
  assert.equal(directives.get('loading'), element.ElLoading.directive)
  for (const name of ['loading', 'message', 'message-box']) {
    assert.ok(plugin.includes('components/' + name + '/style/css'))
  }
  const main = readFileSync(new URL('../src/main.ts', import.meta.url), 'utf8')
  assert.ok(main.includes('installElement(app)'))
  assert.ok(!main.includes('app.use(ElementPlus)'))
  assert.ok(!main.includes('element-plus/dist/index.css'))
})
