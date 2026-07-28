<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { workflowApi } from '@/api/workflows'
import { useWatchlistStore } from '@/stores/watchlist'

const router = useRouter()
const watchlist = useWatchlistStore()
const loading = ref(false)
const items = ref<any[]>([])
const selected = ref<any>(null)
const explanation = ref('')
const updatedAt = ref('')
const source = ref('统一情报数据中心')
const sourceUrl = ref('/sources')
const status = ref<'live' | 'unavailable'>('live')
const statusMessage = ref('')
const maxHeat = computed(() => Math.max(...items.value.map(item => Number(item.heat || 0)), 1))

async function load() {
  loading.value = true
  try {
    const data = await workflowApi.getHotRanking()
    items.value = data.items || []
    updatedAt.value = data.updated_at
    source.value = data.source || '统一情报数据中心'
    sourceUrl.value = data.source_url || '/sources'
    status.value = data.status || 'unavailable'
    statusMessage.value = data.message || ''
    if (items.value.length) void selectItem(items.value[0])
  }
  catch {
    items.value = []
    status.value = 'unavailable'
    statusMessage.value = '数据服务暂时不可用，请稍后重新刷新'
  }
  finally { loading.value = false }
}

async function selectItem(item: any) {
  selected.value = item
  explanation.value = '正在生成背景摘要…'
  try { explanation.value = (await workflowApi.explainHotItem(item)).explanation }
  catch { explanation.value = '暂时无法生成背景摘要，可以打开原始来源继续查看。' }
}

function toggleWatch() {
  if (!selected.value) return
  watchlist.toggle({ title: selected.value.title, category: selected.value.category, heat: selected.value.heat, sourceUrl: selected.value.url })
}

onMounted(load)
</script>

<template>
  <div class="monitor-page" :aria-busy="loading">
    <header class="monitor-head">
      <div class="system-title"><span class="status-light" :class="{ offline: status !== 'live' }"></span><div><p>INTELLIGENCE SIGNALS / LIVE</p><h1>真实情报信号榜</h1></div></div>
      <div class="monitor-meta"><router-link :to="sourceUrl">{{ source }}</router-link><strong>{{ updatedAt }}</strong><button type="button" :disabled="loading" title="刷新情报榜" @click="load"><el-icon><Refresh /></el-icon></button></div>
    </header>

    <main class="monitor-grid">
      <section class="ranking-board">
        <header><span>RANK</span><span>TOPIC</span><span>HEAT SIGNAL</span><span>SOURCE</span></header>
        <div v-if="loading && !items.length" class="signal-loading" role="status">
          <span class="signal-bars"><i></i><i></i><i></i><i></i><i></i></span>
          <strong>正在接入公开热榜信号</strong>
          <small>页面其余功能仍可使用</small>
        </div>
        <div v-else-if="!items.length" class="signal-loading" role="status">
          <strong>暂时没有已同步的情报内容</strong>
          <small>{{ statusMessage }}</small>
          <button type="button" class="retry-button" @click="load">重新刷新</button>
        </div>
        <button v-for="(item, index) in items" :key="item.title" type="button" :class="{ active: selected?.title === item.title }" @click="selectItem(item)">
          <span class="rank mono">{{ String(index + 1).padStart(2, '0') }}</span>
          <span class="topic"><strong>{{ item.title }}</strong><small>{{ item.category }}</small></span>
          <span class="heat"><i :style="{ width: `${Math.max(8, Number(item.heat || 0) * 100 / maxHeat)}%` }"></i><em>{{ Number(item.heat || 0).toLocaleString() }}</em></span>
          <span class="source">{{ item.platform }}</span>
        </button>
      </section>

      <aside class="explain-panel">
        <div class="scope"><i></i><i></i><i></i><span></span></div>
        <p class="panel-label">AI CONTEXT</p>
        <h2>{{ selected?.title || '选择一个话题' }}</h2>
        <p class="explanation">{{ explanation || '点击左侧榜单，查看话题为什么升温。' }}</p>
        <dl v-if="selected"><div><dt>来源</dt><dd>{{ selected.platform }}</dd></div><div><dt>热度</dt><dd>{{ Number(selected.heat || 0).toLocaleString() }}</dd></div><div><dt>分类</dt><dd>{{ selected.category }}</dd></div></dl>
        <div class="panel-actions"><button type="button" class="primary" :disabled="!selected" @click="router.push({ path: '/insight', query: { q: selected?.title } })">生成完整洞察<el-icon><Right /></el-icon></button><button type="button" :disabled="!selected" @click="toggleWatch"><el-icon><CollectionTag /></el-icon>{{ selected && watchlist.has(selected.title) ? '取消关注' : '关注这个话题' }}</button><a v-if="selected?.url" :href="selected.url" target="_blank" rel="noreferrer">打开来源</a></div>
      </aside>
    </main>
  </div>
</template>

<style scoped>
.monitor-page { min-height: calc(100vh - 64px); color: #e9f1f8; background: #091018; }
.monitor-head { height: 112px; padding: 0 32px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #22303c; background: #0d151e; }.system-title { display: flex; gap: 14px; align-items: center; }.status-light { width: 10px; height: 10px; border-radius: 50%; background: #45e08a; box-shadow: 0 0 0 6px rgba(69,224,138,.1), 0 0 16px rgba(69,224,138,.7); animation: live 1.6s ease-in-out infinite; }@keyframes live { 50% { opacity: .45; } }.system-title p { margin: 0; color: #55b7ff; font: 800 10px/1 "Cascadia Code", monospace; }.system-title h1 { margin: 7px 0 0; font-size: 31px; }.monitor-meta { display: grid; grid-template-columns: auto auto 34px; gap: 10px; align-items: center; color: #75889a; font-size: 10px; }.monitor-meta strong { color: #c4d0dc; }.monitor-meta button { width: 32px; height: 32px; border: 1px solid #2b3b49; background: #111d28; color: #7fc4ff; cursor: pointer; }
.monitor-grid { min-height: calc(100vh - 176px); display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(360px, .72fr); }.ranking-board { padding: 20px 28px 44px; border-right: 1px solid #22303c; }.ranking-board > header, .ranking-board > button { width: 100%; display: grid; grid-template-columns: 54px minmax(260px, 1fr) minmax(180px, .55fr) 76px; gap: 14px; align-items: center; }.ranking-board > header { height: 38px; padding: 0 14px; color: #5d7182; font: 700 9px/1 "Cascadia Code", monospace; }.ranking-board > button { min-height: 76px; padding: 12px 14px; border: 0; border-top: 1px solid #1d2a35; background: transparent; color: inherit; text-align: left; cursor: pointer; transition: background 160ms ease; }.ranking-board > button:hover, .ranking-board > button.active { background: #101d28; }.ranking-board > button.active { box-shadow: inset 3px 0 #3ba8ff; }.rank { color: #65798a; font-weight: 800; }.ranking-board button:nth-of-type(-n+4) .rank { color: #ff6b66; }.topic strong, .topic small { display: block; }.topic strong { font-size: 14px; }.topic small { margin-top: 5px; color: #687d8f; font-size: 10px; }.heat { position: relative; height: 26px; display: flex; align-items: center; }.heat::before { content: ''; position: absolute; left: 0; right: 0; height: 4px; background: #1c2b36; }.heat i { position: relative; z-index: 1; height: 4px; background: linear-gradient(90deg, #1d8cf8, #43e6a8, #f5b942); }.heat em { position: absolute; right: 0; top: -1px; color: #7890a3; font: 400 9px/1 "Cascadia Code", monospace; }.source { color: #7fc4ff; font: 700 10px/1 "Cascadia Code", monospace; text-transform: uppercase; }
.signal-loading { min-height: 360px; display: grid; place-content: center; justify-items: center; color: #8093a5; }.signal-loading strong { margin-top: 24px; color: #c8d5df; font-size: 15px; }.signal-loading small { margin-top: 7px; }.signal-bars { height: 54px; display: flex; align-items: flex-end; gap: 6px; }.signal-bars i { width: 5px; height: 18px; background: #3ba8ff; animation: signal 1.1s ease-in-out infinite; }.signal-bars i:nth-child(2) { height: 36px; animation-delay: 120ms; }.signal-bars i:nth-child(3) { height: 50px; animation-delay: 240ms; }.signal-bars i:nth-child(4) { height: 29px; animation-delay: 360ms; }.signal-bars i:nth-child(5) { height: 42px; animation-delay: 480ms; }@keyframes signal { 50% { opacity: .25; transform: scaleY(.45); } }
.explain-panel { position: sticky; top: 64px; align-self: start; min-height: calc(100vh - 64px); padding: 48px 38px; background: #0b141d; }.scope { position: relative; width: 180px; height: 180px; margin: 0 auto 36px; border: 1px solid #243847; border-radius: 50%; display: grid; place-items: center; }.scope::before, .scope::after { content: ''; position: absolute; border: 1px solid #1e3342; border-radius: 50%; }.scope::before { inset: 28px; }.scope::after { inset: 58px; }.scope i { position: absolute; background: #1e3342; }.scope i:nth-child(1) { left: 0; right: 0; height: 1px; }.scope i:nth-child(2) { top: 0; bottom: 0; width: 1px; }.scope i:nth-child(3) { width: 7px; height: 7px; border-radius: 50%; background: #4fe0a2; box-shadow: 32px -25px 0 #3ba8ff, -42px 38px 0 #ff6b66; }.scope span { position: absolute; left: 50%; top: 50%; width: 80px; height: 1px; transform-origin: left; background: linear-gradient(90deg, #3ba8ff, transparent); animation: sweep 3s linear infinite; }@keyframes sweep { to { transform: rotate(360deg); } }.panel-label { color: #49b1ff; font: 800 10px/1 "Cascadia Code", monospace; }.explain-panel h2 { margin: 12px 0 18px; font-size: 28px; line-height: 1.35; }.explanation { min-height: 110px; color: #a6b4c2; line-height: 1.8; }.explain-panel dl { margin: 28px 0; border-top: 1px solid #24323f; }.explain-panel dl div { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #24323f; }.explain-panel dt { color: #617587; }.explain-panel dd { margin: 0; color: #e3ecf4; }.panel-actions { display: grid; gap: 9px; }.panel-actions button, .panel-actions a { min-height: 42px; display: flex; justify-content: center; align-items: center; gap: 7px; border: 1px solid #2b4051; color: #9cb0c0; background: transparent; cursor: pointer; }.panel-actions .primary { border-color: #238ce8; color: white; background: #1478cc; }
@media (max-width: 920px) { .monitor-grid { grid-template-columns: 1fr; }.explain-panel { position: relative; top: 0; min-height: auto; }.ranking-board { border-right: 0; }.scope { display: none; } }
@media (max-width: 650px) { .monitor-head { padding: 0 16px; }.monitor-meta span, .monitor-meta strong { display: none; }.ranking-board { padding: 12px; overflow-x: auto; }.ranking-board > header, .ranking-board > button { min-width: 620px; }.explain-panel { padding: 30px 22px; } }
.status-light.offline { background: #e5484d; box-shadow: 0 0 0 6px rgba(229,72,77,.1); animation: none; }
.monitor-meta a { color: #7fc4ff; }
.monitor-meta button:disabled { opacity: .5; cursor: wait; }
.retry-button { margin-top: 18px; padding: 9px 16px; border: 1px solid #2b4051; color: #9fd0ff; background: #111d28; cursor: pointer; }
</style>

<style scoped>
.monitor-page { color: #e8f1ed; background: #0d1915; }
.monitor-head { position: relative; overflow: hidden; border-color: #294039; background: linear-gradient(90deg, rgba(14,32,26,.97), rgba(14,32,26,.76)), url('../assets/images/auth-newsroom.jpg') center 48%/cover; }.monitor-head::after { content: ''; position: absolute; left: 0; right: 0; bottom: 0; height: 2px; background: linear-gradient(90deg, #2da397 0 22%, #de625b 22% 28%, transparent 28%); }.system-title, .monitor-meta { position: relative; z-index: 1; }.system-title p { color: #75d0c3; letter-spacing: .12em; }.monitor-meta button { border-color: #385148; border-radius: 4px; color: #75d0c3; background: rgba(18,43,35,.72); }.monitor-meta a { color: #75d0c3; }
.monitor-grid { grid-template-columns: minmax(0, 1.65fr) minmax(350px, .7fr); }.ranking-board { border-color: #263d35; }.ranking-board > header { color: #668078; }.ranking-board > button { border-color: #21352f; transition: background 160ms ease, transform 160ms ease; }.ranking-board > button:hover, .ranking-board > button.active { background: #14251f; }.ranking-board > button:hover { transform: translateX(3px); }.ranking-board > button.active { box-shadow: inset 3px 0 #35a99d; }.heat::before { background: #20342d; }.heat i { background: linear-gradient(90deg, #39a99e, #63c78e, #d8a63b); }.source { color: #6ec9bd; }
.explain-panel { background: #101f1a; }.scope, .scope::before, .scope::after { border-color: #29473e; }.scope i { background: #29473e; }.scope span { background: linear-gradient(90deg, #43b4a7, transparent); }.panel-label { color: #6ec9bd; letter-spacing: .12em; }.explain-panel dl, .explain-panel dl div { border-color: #294039; }.panel-actions button, .panel-actions a { border-color: #365148; border-radius: 4px; }.panel-actions .primary { border-color: #218d82; background: #167f76; transition: transform 160ms ease, background 160ms ease; }.panel-actions .primary:hover { transform: translateY(-2px); background: #1b9186; }
.signal-bars i { background: #3aab9f; }.retry-button { border-radius: 4px; border-color: #365148; color: #8ed6cc; background: #152820; }
@media (max-width: 920px) { .monitor-grid { grid-template-columns: 1fr; }.explain-panel { border-top: 1px solid #294039; } }
@media (max-width: 650px) {
  .monitor-head { height: 104px; }.system-title h1 { font-size: 25px; }.monitor-meta { grid-template-columns: 34px; }.monitor-meta a, .monitor-meta strong { display: none; }
  .ranking-board { padding: 12px 14px 28px; overflow: visible; }.ranking-board > header, .ranking-board > button { min-width: 0; grid-template-columns: 42px minmax(0, 1fr); }.ranking-board > header span:nth-child(n+3), .ranking-board .heat, .ranking-board .source { display: none; }.ranking-board > button { min-height: 68px; }.topic strong { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
  .explain-panel { padding: 30px 22px; }
}
</style>
