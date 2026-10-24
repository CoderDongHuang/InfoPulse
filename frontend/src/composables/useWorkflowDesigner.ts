import { reactive } from 'vue'
import { ElMessage } from 'element-plus'

/** Local graph editing; independent of tenant loading and API requests. */
export function useWorkflowDesigner() {
  const graph = reactive<any>({ nodes: [{ id: 'start', type: 'start', config: {} }, { id: 'end', type: 'end', config: {} }], edges: [{ source: 'start', target: 'end' }] })
  const node = reactive({ id: '', type: 'agent', configValue: '' })
  const edge = reactive({ source: 'start', target: 'end', condition: 'always' })
  function addNode() {
    if (!node.id || graph.nodes.some((x: any) => x.id === node.id)) return ElMessage.warning('节点 ID 不能为空且必须唯一')
    const config: any = {}
    if (node.type === 'agent') config.prompt_key = node.configValue || 'default'
    if (node.type === 'tool') config.tool_key = node.configValue || 'memory.read'
    if (node.type === 'approval') config.summary = node.configValue || '人工复核'
    if (node.type.startsWith('memory')) config.key = node.configValue || node.id
    graph.nodes.push({ id: node.id, type: node.type, config })
    node.id = ''
  }
  function addEdge() {
    if (!graph.nodes.some((x: any) => x.id === edge.source) || !graph.nodes.some((x: any) => x.id === edge.target)) return ElMessage.warning('请选择有效节点')
    graph.edges.push({ ...edge }); edge.source = edge.target; edge.target = 'end'
  }
  function removeNode(id: string) {
    if (['start', 'end'].includes(id)) return
    graph.nodes = graph.nodes.filter((x: any) => x.id !== id)
    graph.edges = graph.edges.filter((x: any) => x.source !== id && x.target !== id)
  }
  return { graph, node, edge, addNode, addEdge, removeNode }
}
