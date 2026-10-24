import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import * as vue from 'vue'

const source = readFileSync(new URL('../src/composables/useWorkflowDesigner.ts', import.meta.url), 'utf8')
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
function setup() {
  const warnings = []
  const context = { exports: {}, require: name => name === 'vue' ? vue : { ElMessage: { warning: text => warnings.push(text) } } }
  vm.runInNewContext(code, context)
  return { ...context.exports.useWorkflowDesigner(), warnings }
}

test('adding nodes enforces unique IDs and maps agent/tool configuration', () => {
  const x = setup()
  x.node.id = 'research'; x.node.configValue = 'brief'; x.addNode()
  assert.equal(x.graph.nodes.at(-1).config.prompt_key, 'brief')
  x.node.id = 'research'; x.addNode()
  assert.equal(x.graph.nodes.length, 3); assert.equal(x.warnings.length, 1)
  x.node.id = 'lookup'; x.node.type = 'tool'; x.node.configValue = ''; x.addNode()
  assert.equal(x.graph.nodes.at(-1).config.tool_key, 'memory.read')
})

test('invalid edge does not mutate graph; valid edge advances editor selection', () => {
  const x = setup()
  x.edge.target = 'missing'; x.addEdge()
  assert.equal(x.graph.edges.length, 1); assert.equal(x.warnings.length, 1)
  x.edge.target = 'end'; x.addEdge()
  assert.equal(x.graph.edges.length, 2); assert.equal(x.edge.source, 'end')
})

test('deleting a node removes its incoming/outgoing edges and protects endpoints', () => {
  const x = setup()
  x.node.id = 'review'; x.node.type = 'approval'; x.addNode()
  x.graph.edges.push({ source: 'start', target: 'review' }, { source: 'review', target: 'end' })
  x.removeNode('review'); x.removeNode('start'); x.removeNode('end')
  assert.equal(x.graph.nodes.length, 2); assert.equal(x.graph.edges.length, 1)
  assert.equal(x.graph.edges[0].target, 'end')
  const independent = setup()
  x.node.id = 'only-here'; x.addNode()
  assert.equal(independent.graph.nodes.length, 2)
})
