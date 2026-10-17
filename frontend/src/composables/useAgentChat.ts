import { computed, ref } from 'vue'
import { agentApi } from '@/api/agent'
import { knowledgeApi } from '@/api/knowledge'

export function shouldSendMessage(event: Pick<KeyboardEvent, 'key' | 'shiftKey' | 'isComposing' | 'keyCode'>) {
  return event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229
}

export function citationLink(value: unknown) {
  try {
    const url = new URL(String(value))
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : undefined
  } catch { return undefined }
}

export function conversationEventId(active: { event_id?: string | null } | null, query: unknown) {
  // A loaded conversation owns its context, even if the URL still contains an older event.
  return active ? active.event_id || undefined : typeof query === 'string' ? query : undefined
}

// Each request owns an epoch: a late stream/detail response cannot mutate another conversation.
export function useAgentChat(api = agentApi, knowledge = knowledgeApi) {
  const conversations = ref<any[]>([]), active = ref<any>(null), prompt = ref('')
  const streaming = ref(false), busy = ref(false), draft = ref(''), tools = ref<any[]>([])
  const error = ref(''), streamError = ref(''), knowledgeError = ref(''), listError = ref('')
  const knowledgeBases = ref<any[]>([]), selectedKnowledge = ref<string[]>([])
  const useFavorites = ref(false), stopped = ref(false)
  let connection: { close: () => void } | undefined, streamEpoch = 0, operationEpoch = 0, listEpoch = 0
  const canSend = computed(() => !!prompt.value.trim() && !streaming.value && !busy.value)

  async function loadList() {
    const epoch = ++listEpoch
    try {
      const result = await api.list()
      if (epoch === listEpoch) { conversations.value = result; listError.value = '' }
    } catch { if (epoch === listEpoch) listError.value = '历史会话加载失败，请重试。' }
  }
  async function loadKnowledge() {
    try { knowledgeBases.value = await knowledge.bases(); knowledgeError.value = '' }
    catch { knowledgeError.value = '知识库暂不可用，仍可使用公开情报对话。' }
  }
  function stop(keepDraft = true) {
    ++streamEpoch
    connection?.close(); connection = undefined
    stopped.value = keepDraft && streaming.value
    streaming.value = false
    if (!keepDraft) { draft.value = ''; tools.value = []; streamError.value = ''; stopped.value = false }
  }
  async function open(id: string) {
    const epoch = ++operationEpoch
    stop(false); busy.value = true; error.value = ''
    try {
      const result = await api.detail(id)
      if (epoch !== operationEpoch) return false
      active.value = result; prompt.value = ''; return true
    } catch { if (epoch === operationEpoch) error.value = '会话加载失败，请重新选择会话。'; return false }
    finally { if (epoch === operationEpoch) busy.value = false }
  }
  async function create(eventId?: string, title = '新会话') {
    if (busy.value) return false
    const epoch = ++operationEpoch
    stop(false); busy.value = true; error.value = ''
    try {
      const result = await api.create({ title, event_id: eventId || null, context_config: { source: eventId ? 'event' : 'manual' } })
      if (epoch !== operationEpoch) return false
      active.value = { ...result, messages: [] }
      void loadList(); return true
    } catch { if (epoch === operationEpoch) error.value = '新建会话失败，输入内容已保留。'; return false }
    finally { if (epoch === operationEpoch) busy.value = false }
  }
  async function remove(id: string) {
    if (busy.value || streaming.value) return false
    busy.value = true; error.value = ''
    try {
      await api.remove(id)
      ++listEpoch
      conversations.value = conversations.value.filter(item => item.id !== id)
      if (active.value?.id === id) { active.value = null; prompt.value = ''; stop(false) }
      return true
    } catch { error.value = '删除失败，会话已保留。'; return false }
    finally { busy.value = false }
  }
  async function send(eventId?: string) {
    if (!canSend.value) return
    const content = prompt.value.trim()
    if (!active.value && !await create(eventId, Array.from(content).slice(0, 40).join(''))) return
    const target = active.value
    const epoch = ++streamEpoch
    target.messages.push({ id: `local-${Date.now()}`, role: 'user', content, citations: [] })
    prompt.value = ''; draft.value = ''; tools.value = []; streamError.value = ''; stopped.value = false; streaming.value = true
    const fail = (message: string) => {
      if (epoch !== streamEpoch) return
      ++streamEpoch; connection?.close(); connection = undefined; streaming.value = false
      streamError.value = message || '回复失败，请重试。'
      if (!prompt.value) prompt.value = content
    }
    try {
      connection = api.send(target.id, { content, context_additions: useFavorites.value ? [{ type: 'favorite' }] : [], knowledge_base_ids: [...selectedKnowledge.value] }, (type, data) => {
        if (epoch !== streamEpoch || active.value?.id !== target.id) return
        if (type === 'message.delta') draft.value += data.text || ''
        if (type === 'tool.started') tools.value.push({ ...data, status: 'running' })
        if (type === 'tool.completed') {
          const tool = [...tools.value].reverse().find(item => item.name === data.name)
          if (tool) Object.assign(tool, data, { status: 'completed' })
        }
        if (type === 'message.completed') {
          target.messages.push(data); draft.value = ''; streaming.value = false
          ++streamEpoch; connection = undefined; void loadList()
        }
        if (type === 'message.failed' || type === 'error') fail(data.message || '连接中断，输入已恢复；可重新发送。')
      })
    } catch { fail('发送失败，输入已恢复；请检查连接后重试。') }
  }
  function dispose() { ++operationEpoch; ++listEpoch; busy.value = false; stop(false) }
  return { conversations, active, prompt, streaming, busy, draft, tools, error, streamError, knowledgeError, listError,
    knowledgeBases, selectedKnowledge, useFavorites, stopped, canSend, loadList, loadKnowledge, open, create, remove, send, stop, dispose }
}
