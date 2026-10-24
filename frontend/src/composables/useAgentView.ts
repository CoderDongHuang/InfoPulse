import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { agentApi } from '@/api/agent'
import { citationLink, conversationEventId, shouldSendMessage, useAgentChat } from '@/composables/useAgentChat'

/**
 * State and actions for the Agent screen. Keeping this outside the view makes
 * the conversation lifecycle independently testable and keeps the template
 * focused on presentation.
 */
export function useAgentView() {
  const route = useRoute()
  const router = useRouter()
  const chat = reactive(useAgentChat())
  const historySearch = ref('')
  const sidebarOpen = ref(false)
  const citation = ref<any>(null)
  const messagesEl = ref<HTMLElement>()
  const inputEl = ref<HTMLTextAreaElement>()
  const historyToggle = ref<HTMLButtonElement>()
  const feedbackBusy = ref<string>()
  const feedbackGiven = ref<Record<string, string>>({})
  const visibleHistory = computed(() => chat.conversations.filter(c => c.title?.toLowerCase().includes(historySearch.value.toLowerCase())))
  const hasMessages = computed(() => !!chat.active?.messages?.length)
  const citationOpen = computed({ get: () => !!citation.value, set: value => { if (!value) citation.value = null } })
  const eventId = () => conversationEventId(chat.active, route.query.event_id)
  const quick = ['总结今天 AI 行业的公开情报', '比较近期事件中的主要观点', '梳理事件的时间线与证据']

  async function syncLocation() {
    const query = { ...route.query }
    if (chat.active?.id) query.conversation = chat.active.id
    else delete query.conversation
    if (chat.active) {
      if (chat.active.event_id) query.event_id = chat.active.event_id
      else delete query.event_id
    }
    if (query.conversation !== route.query.conversation || query.event_id !== route.query.event_id) await router.replace({ query })
  }
  async function closeSidebar() { sidebarOpen.value = false; await nextTick(); historyToggle.value?.focus() }
  async function open(id: string) { if (await chat.open(id)) { await syncLocation(); sidebarOpen.value = false } }
  async function create() {
    if (await chat.create(eventId())) { chat.prompt = ''; await syncLocation(); sidebarOpen.value = false; inputEl.value?.focus() }
  }
  async function send() { await chat.send(eventId()); await syncLocation() }
  function keydown(event: KeyboardEvent) { if (shouldSendMessage(event)) { event.preventDefault(); void send() } }
  async function remove(id: string) {
    try { await ElMessageBox.confirm('删除后无法恢复，确定删除这个会话？', '删除会话', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }) }
    catch { return }
    if (await chat.remove(id)) await syncLocation()
  }
  async function feedback(message: any, rating: string) {
    if (feedbackBusy.value) return
    feedbackBusy.value = message.id
    try { await agentApi.feedback(chat.active.id, message.id, rating); feedbackGiven.value[message.id] = rating; ElMessage.success('反馈已记录') }
    catch { ElMessage.error('反馈提交失败，请重试') }
    finally { feedbackBusy.value = undefined }
  }
  async function copy(content: string) {
    try { await navigator.clipboard.writeText(content); ElMessage.success('已复制回答') }
    catch { ElMessage.error('复制失败，请手动选择文本复制') }
  }
  async function resizeInput() { await nextTick(); const el = inputEl.value; if (el) { el.style.height = 'auto'; el.style.height = `${Math.min(el.scrollHeight, 180)}px` } }
  async function scroll() { await nextTick(); messagesEl.value?.scrollTo({ top: messagesEl.value.scrollHeight }) }
  function useQuick(text: string) { chat.prompt = text; inputEl.value?.focus() }
  watch(() => chat.prompt, resizeInput)
  watch(() => [chat.draft, chat.active?.messages?.length, chat.tools.length], scroll)
  watch(() => route.query.conversation, async id => {
    if (typeof id === 'string' && id !== chat.active?.id) await chat.open(id)
    else if (!id && chat.active) { chat.dispose(); chat.active = null; chat.prompt = '' }
  })
  onMounted(async () => {
    void chat.loadList(); void chat.loadKnowledge()
    if (typeof route.query.conversation === 'string') await chat.open(route.query.conversation)
    await resizeInput()
  })
  onBeforeUnmount(chat.dispose)

  return {
    route, router, chat, historySearch, sidebarOpen, citation, messagesEl, inputEl, historyToggle,
    feedbackBusy, feedbackGiven, visibleHistory, hasMessages, citationOpen, eventId, quick,
    citationLink, closeSidebar, open, create, send, keydown, remove, feedback, copy, useQuick,
  }
}
