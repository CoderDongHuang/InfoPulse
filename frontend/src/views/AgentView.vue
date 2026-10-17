<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowUp, ChatDotRound, Check, Close, CopyDocument, Delete, Document, Fold, Plus, Search, Star } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { agentApi } from '@/api/agent'
import { citationLink, conversationEventId, shouldSendMessage, useAgentChat } from '@/composables/useAgentChat'

const route = useRoute(), router = useRouter(), chat = reactive(useAgentChat())
const historySearch = ref(''), sidebarOpen = ref(false), citation = ref<any>(null)
const messagesEl = ref<HTMLElement>(), inputEl = ref<HTMLTextAreaElement>(), historyToggle = ref<HTMLButtonElement>()
const feedbackBusy = ref<string>(), feedbackGiven = ref<Record<string, string>>({})
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
</script>

<template>
  <section class="agent" aria-label="AI 对话" @keydown.esc="sidebarOpen && closeSidebar()">
    <button v-if="sidebarOpen" class="sidebar-backdrop" aria-label="关闭历史会话" @click="closeSidebar" />
    <aside id="chat-history" class="history" :class="{ 'is-open': sidebarOpen }" aria-label="会话历史">
      <div class="history-brand"><el-icon><ChatDotRound /></el-icon><strong>InfoPulse <span>AI</span></strong><button class="icon-button mobile-close" aria-label="关闭历史会话" @click="closeSidebar"><el-icon><Close /></el-icon></button></div>
      <button class="new-chat" :disabled="chat.busy" @click="create"><el-icon><Plus /></el-icon>开启新对话<kbd>＋</kbd></button>
      <label class="history-search"><el-icon><Search /></el-icon><input v-model="historySearch" placeholder="搜索历史会话" aria-label="搜索历史会话" /></label>
      <div class="history-caption">历史会话</div>
      <p v-if="chat.listError" class="history-error" role="alert">{{ chat.listError }}<button @click="chat.loadList">重试</button></p>
      <nav class="history-list" aria-label="历史对话">
        <div v-for="c in visibleHistory" :key="c.id" class="history-item" :class="{ active: chat.active?.id === c.id }">
          <button class="history-link" :disabled="chat.busy" :aria-current="chat.active?.id === c.id ? 'page' : undefined" @click="open(c.id)"><span>{{ c.title }}</span><small v-if="c.event_id">事件对话</small></button>
          <button class="icon-button delete-chat" :disabled="chat.busy || chat.streaming" :aria-label="`删除会话：${c.title}`" @click="remove(c.id)"><el-icon><Delete /></el-icon></button>
        </div>
        <p v-if="!visibleHistory.length && !chat.listError" class="history-empty">{{ historySearch ? '没有匹配的会话' : '你的思考，从这里开始' }}</p>
      </nav>
      <div class="history-bottom"><span class="brand-dot" />让每一条信息，都成为洞察</div>
    </aside>

    <div class="chat" :class="{ 'is-empty': !hasMessages }" :aria-busy="chat.busy">
      <header class="chat-header">
        <button ref="historyToggle" class="icon-button history-toggle" aria-label="打开历史会话" aria-controls="chat-history" :aria-expanded="sidebarOpen" @click="sidebarOpen = !sidebarOpen"><el-icon><Fold /></el-icon></button>
        <div class="chat-title"><strong>{{ hasMessages ? chat.active?.title : 'InfoPulse AI' }}</strong><span>情报研究助手</span></div>
        <span v-if="chat.active?.event_id || eventId()" class="event-badge">事件上下文</span>
        <button class="icon-button header-new" aria-label="新建会话" :disabled="chat.busy" @click="create"><el-icon><Plus /></el-icon></button>
      </header>
      <div v-if="chat.error" class="chat-error" role="alert">{{ chat.error }}</div>

      <div ref="messagesEl" class="messages" :class="{ 'welcome-area': !hasMessages }">
        <div v-if="!hasMessages" class="welcome">
          <div class="welcome-heading"><span class="assistant-mark"><el-icon><ChatDotRound /></el-icon></span><h1>我是 InfoPulse，很高兴见到你！</h1></div>
          <p>从公开情报到私有知识，和你一起发现信息背后的价值。</p>
        </div>
        <div v-else class="message-list">
          <article v-for="m in chat.active.messages" :key="m.id" class="message" :class="m.role">
            <span v-if="m.role === 'assistant'" class="assistant-mark small"><el-icon><ChatDotRound /></el-icon></span>
            <div class="message-body"><p>{{ m.content || (m.status === 'failed' ? '这条回复生成失败，请重新发送问题。' : m.status === 'cancelled' ? '这条回复已停止。' : m.status === 'streaming' ? '这条回复尚未完成，请稍后重新打开会话确认状态。' : '') }}</p>
              <div v-if="m.citations?.length" class="citations"><button v-for="(c, index) in m.citations" :key="c.id || index" @click="citation = c"><el-icon><Document /></el-icon>{{ Number(index) + 1 }} · {{ c.source || c.title || '查看来源' }}</button></div>
              <div v-if="m.role === 'assistant' && m.content && m.status === 'completed'" class="feedback">
                <button class="icon-button" aria-label="复制回答" @click="copy(m.content)"><el-icon><CopyDocument /></el-icon></button>
                <button :class="{ selected: feedbackGiven[m.id] === 'up' }" :disabled="!!feedbackBusy" @click="feedback(m, 'up')">有帮助</button>
                <button :class="{ selected: feedbackGiven[m.id] === 'down' }" :disabled="!!feedbackBusy" @click="feedback(m, 'down')">需改进</button>
              </div>
            </div>
          </article>
          <div v-if="chat.tools.length" class="tools" aria-label="检索过程"><div v-for="(tool, index) in chat.tools" :key="index"><el-icon v-if="tool.status === 'completed'"><Check /></el-icon><span v-else>·</span>{{ tool.name === 'search' ? '检索公开情报' : tool.name === 'knowledge_base' ? '检索私有知识' : '读取上下文' }}<small v-if="tool.count !== undefined">{{ tool.count }} 条证据</small></div></div>
          <article v-if="chat.draft || chat.streaming" class="message assistant streaming-message"><span class="assistant-mark small"><el-icon><ChatDotRound /></el-icon></span><div class="message-body"><p>{{ chat.draft || '正在整理信息…' }}</p><small v-if="chat.stopped || chat.streamError">未完成的回复，仅保留在当前页面</small></div></article>
          <p v-if="chat.stopped" class="stream-notice" role="status">已停止生成。可以继续发送新问题。</p>
          <p v-if="chat.streamError" class="chat-error" role="alert">{{ chat.streamError }}</p>
        </div>
      </div>

      <div class="composer-area">
        <div class="composer">
          <textarea ref="inputEl" v-model="chat.prompt" rows="1" maxlength="8000" aria-label="输入问题" placeholder="给 InfoPulse 发送消息" @keydown="keydown" />
          <div class="composer-toolbar"><div class="context-options">
            <span class="context-chip public-context" title="检索本机已采集的公开情报，不是实时网页搜索"><el-icon><Search /></el-icon>公开情报</span>
            <button class="context-chip" :class="{ selected: chat.useFavorites }" :aria-pressed="chat.useFavorites" :disabled="chat.streaming" @click="chat.useFavorites = !chat.useFavorites"><el-icon><Star /></el-icon>收藏</button>
            <details class="knowledge-picker"><summary class="context-chip"><el-icon><Document /></el-icon>知识库<span v-if="chat.selectedKnowledge.length">{{ chat.selectedKnowledge.length }}</span></summary>
              <div class="knowledge-options"><p v-if="chat.knowledgeError" role="alert">{{ chat.knowledgeError }}<button @click="chat.loadKnowledge">重试</button></p><p v-else-if="!chat.knowledgeBases.length">暂无知识库，请先在知识管理中导入文档。</p><label v-for="base in chat.knowledgeBases" :key="base.id"><input v-model="chat.selectedKnowledge" type="checkbox" :value="base.id" :disabled="chat.streaming" />{{ base.name }}</label></div>
            </details>
          </div>
          <button v-if="chat.streaming" class="send-button stop-button" aria-label="停止生成" @click="chat.stop()"><span /></button>
          <button v-else class="send-button" aria-label="发送消息" :disabled="!chat.canSend" @click="send"><el-icon><ArrowUp /></el-icon></button></div>
        </div>
        <div v-if="!hasMessages" class="quick-prompts"><button v-for="q in quick" :key="q" @click="useQuick(q)">{{ q }}</button></div>
        <p class="disclaimer">基于已采集情报与所选知识库回答，请核对引用。未配置模型时提供证据摘要。<span>Enter 发送 · Shift + Enter 换行</span></p>
      </div>
    </div>
    <el-drawer v-model="citationOpen" title="回答引用" size="min(480px,92%)"><template v-if="citation"><h3>{{ citation.title }}</h3><p>{{ citation.citation_type === 'private' ? '私有知识' : '公开来源' }} · {{ citation.source }}</p><blockquote>{{ citation.quote }}</blockquote><p v-if="citation.citation_type === 'private'">{{ citation.page ? `第 ${citation.page} 页` : '' }} {{ citation.paragraph ? `第 ${citation.paragraph} 段` : '' }}</p><a v-else-if="citationLink(citation.url)" :href="citationLink(citation.url)" target="_blank" rel="noopener noreferrer">打开原文</a></template></el-drawer>
  </section>
</template>

<style scoped>
.agent{--chat-blue:#4d6bfe;display:flex;height:calc(100dvh - 124px);min-height:540px;background:#fff;color:#262b36;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif}
.agent button,.agent input,.agent textarea{font:inherit}.agent button{cursor:pointer}.agent button:disabled{cursor:not-allowed;opacity:.5}.agent button:focus-visible,.agent summary:focus-visible,.agent input:focus-visible{outline:2px solid var(--chat-blue);outline-offset:3px}.agent .el-icon{flex-shrink:0}.icon-button{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;padding:0;border:0;border-radius:8px;background:transparent;color:#737b8c;flex-shrink:0}.icon-button:hover{background:#e9ecf3;color:#293953}
.history{display:flex;flex-direction:column;flex-shrink:0;width:250px;padding:26px 16px 18px;background:#f8f9fb;border-right:1px solid #f0f1f4;min-width:0}.history-brand{display:flex;align-items:center;gap:10px;padding:0 10px 25px;font-size:20px;letter-spacing:-.5px}.history-brand>.el-icon{color:var(--chat-blue);font-size:28px}.history-brand span{font-size:13px;font-weight:500;color:#8893a6;letter-spacing:0}.new-chat{display:flex;align-items:center;gap:9px;width:100%;padding:13px 16px;border:0;border-radius:14px;background:#e8edff;color:#3c5bdc;font-size:14px!important}.new-chat kbd{margin-left:auto;color:#8394d2}.history-search{display:flex;align-items:center;gap:9px;padding:12px 10px;margin-top:12px;color:#9298a5}.history-search input{width:100%;min-width:0;border:0;background:transparent;outline:0;font-size:12px}.history-caption{padding:16px 10px 10px;color:#9298a5;font-size:11px}.history-list{flex:1;min-height:0;overflow:auto}.history-item{display:flex;align-items:center;border-radius:10px;margin:3px 0}.history-item:hover,.history-item.active{background:#e9edf5}.history-link{min-width:0;flex:1;display:flex;flex-direction:column;gap:4px;text-align:left;padding:12px 10px;border:0;background:transparent;color:#4e5666;font-size:13px!important}.history-link span{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.history-link small{font-size:10px;color:#8b94a5}.delete-chat{margin-right:3px;width:28px}.history-empty,.history-error{padding:10px;font-size:12px;color:#7b8495;line-height:1.8}.history-bottom{display:flex;align-items:center;gap:8px;padding:20px 8px 2px;color:#9097a3;font-size:10px}.brand-dot{width:6px;height:6px;border-radius:50%;background:#7b91ec}
.chat{flex:1;min-width:0;display:flex;flex-direction:column}.chat-header{height:68px;flex-shrink:0;display:flex;align-items:center;gap:12px;padding:0 32px}.chat-title{min-width:0;display:flex;align-items:center;gap:13px}.chat-title strong{font-size:16px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.chat-title>span{font-size:11px;color:#a3a9b5;white-space:nowrap}.header-new{margin-left:auto}.event-badge{font-size:10px;color:#6075bd;background:#eff3ff;border-radius:20px;padding:5px 9px;white-space:nowrap}.messages{flex:1;min-height:0;overflow-y:auto;padding:26px 32px 10px;scrollbar-width:thin}.message-list{max-width:800px;margin:auto}.welcome-area{display:flex;align-items:flex-end;justify-content:center;padding-bottom:32px}.welcome{text-align:center;width:100%}.welcome-heading{display:flex;align-items:center;justify-content:center;gap:14px}.welcome h1{font-size:27px;line-height:1.5;letter-spacing:-.7px;font-weight:600;margin:0}.welcome p{font-size:14px;color:#8a909e;line-height:1.9;margin:15px 0 0}.assistant-mark{display:inline-flex;align-items:center;justify-content:center;color:var(--chat-blue);font-size:43px;flex-shrink:0}.assistant-mark.small{font-size:25px;width:34px;height:36px;margin-right:14px}.message{display:flex;gap:0;margin-bottom:32px}.message-body{min-width:0;flex:1}.message-body>p{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px;line-height:1.95;margin:3px 0 12px}.message.user{justify-content:flex-end;margin-bottom:34px}.user .message-body{flex:initial;max-width:85%;padding:12px 20px;background:#edf2ff;border-radius:22px}.user .message-body>p{margin:0}.citations{display:flex;flex-wrap:wrap;gap:7px}.citations button{display:flex;align-items:center;gap:5px;max-width:100%;overflow-wrap:anywhere;text-align:left;font-size:11px;background:#f5f7fb;border:1px solid #e9edf4;border-radius:8px;padding:6px 8px;color:#52699c}.feedback{display:flex;align-items:center;gap:12px;margin-top:10px}.feedback button{background:transparent;border:0;color:#929aaa;font-size:11px}.feedback button.selected{color:var(--chat-blue)}.feedback .icon-button{width:26px;height:26px;font-size:15px}.tools{font-size:11px;color:#8a93a2;margin:0 0 18px 48px}.tools>div{display:flex;align-items:center;gap:7px;padding:4px 0}.tools small{color:#9ca5b3}.stream-notice,.streaming-message small{font-size:12px;color:#8d96a6}.chat-error{margin:8px 32px;color:#a84b40;font-size:12px;line-height:1.7;background:#fff6f3;border-radius:10px;padding:10px 14px}
.composer-area{width:min(800px,calc(100% - 64px));margin:0 auto;flex-shrink:0;padding-top:8px}.is-empty .composer-area{padding-bottom:clamp(28px,17vh,180px)}.composer{padding:19px 20px 13px;background:#f5f6f8;border:1px solid #eceef2;border-radius:32px;box-shadow:0 2px 7px #19254903}.composer:focus-within{border-color:#cbd4f8}.composer textarea{display:block;width:100%;min-height:30px;max-height:180px;resize:none;border:0;outline:0;background:transparent;color:#333c4c;line-height:1.7;font-size:14px;padding:0 3px;margin:0 0 12px}.composer textarea::placeholder{color:#a1a6b2}.composer-toolbar{display:flex;align-items:center;justify-content:space-between;gap:8px}.context-options{display:flex;align-items:center;gap:7px;min-width:0;flex-wrap:wrap}.context-chip{display:inline-flex;align-items:center;gap:5px;border:1px solid #dce1eb;background:#fff;color:#626c7c;font-size:11px!important;border-radius:18px;padding:5px 9px;line-height:1.5;white-space:nowrap}.context-chip.selected{color:#4864dc;background:#eaf0ff;border-color:#bdcbff}.public-context{background:transparent;border-color:transparent;color:#8e97a7}.knowledge-picker{position:relative}.knowledge-picker summary{list-style:none;cursor:pointer}.knowledge-picker summary::-webkit-details-marker{display:none}.knowledge-options{position:absolute;bottom:38px;left:0;z-index:5;width:230px;max-height:220px;overflow:auto;padding:12px;border:1px solid #e1e5ef;border-radius:14px;background:#fff;box-shadow:0 8px 28px #25356016;font-size:12px}.knowledge-options label{display:flex;align-items:center;gap:8px;padding:9px 3px;overflow-wrap:anywhere}.knowledge-options input{accent-color:var(--chat-blue)}.knowledge-options p{color:#818b9a;line-height:1.8;margin:0}.send-button{display:flex;align-items:center;justify-content:center;width:36px;height:36px;flex-shrink:0;border:0;border-radius:50%;background:var(--chat-blue);color:#fff;font-size:23px!important}.send-button:disabled{background:#d9dce3;opacity:1!important;color:white}.stop-button span{width:12px;height:12px;border-radius:2px;background:#fff}.quick-prompts{display:flex;justify-content:center;gap:9px;flex-wrap:wrap;margin:19px 0 0}.quick-prompts button{font-size:11px;color:#7b8597;border:1px solid #ebedf2;background:#fff;padding:8px 12px;border-radius:18px}.quick-prompts button:hover{color:var(--chat-blue);border-color:#c9d3fa}.disclaimer{text-align:center;color:#a4aab6;font-size:10px;line-height:1.8;margin:13px 0 12px}.disclaimer span{display:block;font-size:9px;margin-top:2px}.history-toggle,.mobile-close,.sidebar-backdrop{display:none}blockquote{padding:16px;margin:16px 0;border-left:3px solid #6f87e9;background:#f5f7fc;line-height:1.8;white-space:pre-wrap;overflow-wrap:anywhere}
@media(max-width:1100px){.history{width:218px;padding-inline:12px}.welcome h1{font-size:23px}.chat-header{padding:0 22px}.composer-area{width:calc(100% - 44px)}.welcome-heading{gap:10px}.welcome-heading>.assistant-mark{font-size:35px}}
@media(max-width:760px){.agent{min-height:500px;position:relative}.history{display:none;position:absolute;inset:0 auto 0 0;z-index:20;width:260px;box-shadow:10px 0 35px #24345418}.history.is-open{display:flex}.history-toggle,.mobile-close{display:inline-flex}.mobile-close{margin-left:auto}.history-brand{padding-inline:4px;font-size:17px}.sidebar-backdrop{display:block;position:absolute;inset:0;z-index:19;background:#19263d35;border:0}.chat-header{height:58px;padding:0 16px;gap:8px}.chat-title{gap:8px}.chat-title strong{font-size:14px}.chat-title>span{display:none}.messages{padding:22px 18px 10px}.welcome-area{padding-bottom:26px}.welcome-heading{flex-direction:column;gap:14px}.welcome h1{font-size:21px;letter-spacing:-.5px}.welcome p{font-size:12px;max-width:290px;margin:13px auto 0}.composer-area{width:calc(100% - 28px)}.is-empty .composer-area{padding-bottom:clamp(24px,10vh,90px)}.composer{border-radius:29px;padding:17px 15px 12px}.composer textarea{font-size:14px}.context-options{gap:4px}.context-chip{font-size:10px!important;padding:5px 7px}.public-context{padding-left:0;padding-right:0}.quick-prompts{gap:7px}.quick-prompts button{font-size:10px}.disclaimer{font-size:9px}.assistant-mark.small{margin-right:8px;width:27px;font-size:23px}.knowledge-options{left:auto;right:0;width:220px}.message-body>p{font-size:13px}.chat-error{margin:8px 14px}.tools{margin-left:35px}}
@media(max-width:720px){.agent{height:calc(100dvh - 120px)}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
</style>
