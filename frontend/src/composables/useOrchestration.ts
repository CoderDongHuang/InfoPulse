import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { enterpriseApi, selectTenant, type TenantContext } from '@/api/enterprise'
import { orchestrationApi as api } from '@/api/orchestration'
import { useWorkflowDesigner } from '@/composables/useWorkflowDesigner'

/** Business state for the orchestration console, extracted from the view so
 * API workflows can be tested without mounting the full page. */
export function useOrchestration() {
  const tab = ref('overview')
  const loading = ref(true)
  const ctx = ref<TenantContext | null>(null)
  const overview = ref<any>({})
  const workflows = ref<any[]>([])
  const runs = ref<any[]>([])
  const approvals = ref<any[]>([])
  const tools = ref<any[]>([])
  const prompts = ref<any[]>([])
  const routes = ref<any[]>([])
  const datasets = ref<any[]>([])
  const templates = ref<any[]>([])
  const memories = ref<any[]>([])
  const selected = ref<any>()
  const runDetail = ref<any>()
  const evalResult = ref<any>()
  const { graph, node, edge, addNode, addEdge, removeNode } = useWorkflowDesigner()
  const flow = reactive({ name: '', description: '', change_note: 'Initial version' })
  const prompt = reactive({ key: '', system_prompt: '', input_variables: [] as string[], status: 'active' })
  const route = reactive({ task_type: 'general', primary_model: '', fallback_models: [] as string[], max_cost_cents: 100, max_tokens: 4000, enabled: true })
  const dataset = reactive({ name: '', cases: '[{"name":"baseline","input":{},"forbidden_tools":[]}]', threshold: .8 })
  const memory = reactive({ namespace: 'workflow', key: '', value: '{}', ttl_seconds: 86400 })
  const runForm = reactive({ budget_cents: 100, input: '{}' })
  const templateForm = reactive({ key: '', name: '', category: 'operations', published: true })
  const can = (permission: string) => ctx.value?.permissions.includes(permission)
  const pending = computed(() => approvals.value.filter(x => x.status === 'pending'))

  async function load() {
    loading.value = true
    try {
      ctx.value = await enterpriseApi.context()
      selectTenant(ctx.value.organization.id, ctx.value.workspaces[0]?.id)
      ;[overview.value, workflows.value, runs.value, approvals.value, tools.value, prompts.value, routes.value, datasets.value, templates.value, memories.value] = await Promise.all([
        api.overview(), api.workflows(), api.runs(), api.approvals(), api.tools(), api.prompts(), api.routes(), api.datasets(), api.templates(), api.memories(),
      ])
    } finally { loading.value = false }
  }
  async function createFlow() { await api.createWorkflow({ ...flow, workspace_id: ctx.value?.workspaces[0]?.id, graph }); flow.name = ''; await load(); ElMessage.success('工作流草稿已创建') }
  async function openFlow(id: string) { selected.value = await api.workflow(id); const active = selected.value.versions.find((x: any) => x.id === selected.value.active_version_id) || selected.value.versions[0]; Object.assign(graph, JSON.parse(JSON.stringify(active.graph))); tab.value = 'designer' }
  async function newVersion() { await api.version(selected.value.id, { graph, change_note: 'Designer update' }); selected.value = await api.workflow(selected.value.id); ElMessage.success('不可变版本已创建') }
  async function startRun(workflow: any) { const result = await api.start(workflow.id, { budget_cents: runForm.budget_cents, input: JSON.parse(runForm.input), idempotency_key: `ui:${workflow.id}:${Date.now()}` }); await load(); await openRun(result.id) }
  async function openRun(id: string) { runDetail.value = await api.run(id); tab.value = 'trace' }
  async function decide(id: string, decision: string) { await api.decide(id, { decision, note: '已在 Agent 编排控制台复核风险与输入' }); await load(); if (runDetail.value) runDetail.value = await api.run(runDetail.value.id) }
  async function savePolicy(tool: any, effect: string) { await api.policy({ tool_id: tool.id, workspace_id: ctx.value?.workspaces[0]?.id, effect, require_approval: true, max_calls_per_run: 3, constraints: {} }); tools.value = await api.tools() }
  async function addPrompt() { await api.createPrompt(prompt); prompts.value = await api.prompts(); prompt.key = ''; prompt.system_prompt = '' }
  async function saveRoute() { await api.saveRoute({ ...route, workspace_id: ctx.value?.workspaces[0]?.id }); routes.value = await api.routes() }
  async function addDataset() { await api.createDataset({ name: dataset.name, cases: JSON.parse(dataset.cases), thresholds: { minimum_score: dataset.threshold } }); datasets.value = await api.datasets(); dataset.name = '' }
  async function runEval(item: any) { const version = selected.value?.versions?.[0]?.id; if (!version) return ElMessage.warning('先打开一个工作流'); evalResult.value = await api.evaluate(item.id, version); ElMessage[evalResult.value.passed ? 'success' : 'warning'](`评测得分 ${evalResult.value.score}`) }
  async function addMemory() { await api.putMemory({ ...memory, workspace_id: ctx.value?.workspaces[0]?.id, value: JSON.parse(memory.value) }); memories.value = await api.memories(); memory.key = '' }
  async function publishTemplate() { await api.createTemplate({ ...templateForm, graph }); templates.value = await api.templates() }

  onMounted(load)
  return {
    tab, loading, ctx, overview, workflows, runs, approvals, tools, prompts, routes, datasets, templates, memories,
    selected, runDetail, evalResult, graph, flow, node, edge, prompt, route, dataset, memory, runForm, templateForm,
    can, pending, load, addNode, addEdge, removeNode, createFlow, openFlow, newVersion, startRun, openRun, decide,
    savePolicy, addPrompt, saveRoute, addDataset, runEval, addMemory, publishTemplate, api,
  }
}
