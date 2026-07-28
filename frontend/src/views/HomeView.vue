<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { workflowApi } from '@/api/workflows'

const router = useRouter()
const loading = ref(false)
const hotItems = ref<any[]>([])
const updatedAt = ref('')
const sourceUrl = ref('/sources')
const sourceStatus = ref<'live' | 'unavailable'>('live')
const statusMessage = ref('正在读取已同步的真实情报数据')

const lead = computed(() => hotItems.value[0])
const categoryCount = computed(() => new Set(hotItems.value.map(item => item.category).filter(Boolean)).size)
const topHeat = computed(() => Number(lead.value?.heat || 0))

const workflows = [
  { path: '/insight', icon: 'DataAnalysis', code: '01', title: '热点洞察', description: '聚合微博、B站与贴吧公开讨论，查看情绪、观点和来源。', action: '开始分析', tone: 'cyan' },
  { path: '/mouthpiece', icon: 'EditPen', code: '02', title: '表达工作室', description: '保留你的事实与立场，把草稿调整为适合发布的完整表达。', action: '整理文案', tone: 'coral' },
  { path: '/timeline', icon: 'Clock', code: '03', title: '事件脉络', description: '按照时间、来源和可信度整理碎片信息，形成可回溯档案。', action: '建立时间线', tone: 'gold' },
]

function formatHeat(value: number) {
  if (value >= 10_000_000) return `${(value / 10_000_000).toFixed(1)} 千万`
  if (value >= 10_000) return `${Math.round(value / 10_000)} 万`
  return value.toLocaleString('zh-CN')
}

async function loadDashboard() {
  loading.value = true
  try {
    const data = await workflowApi.getHotRanking()
    hotItems.value = data.items || []
    updatedAt.value = data.updated_at || ''
    sourceUrl.value = data.source_url || sourceUrl.value
    sourceStatus.value = data.status || 'unavailable'
    statusMessage.value = data.message || (hotItems.value.length ? '来自已同步官方 API 与 RSS 的真实内容' : '请先到数据源中心执行同步')
  } catch {
    hotItems.value = []
    sourceStatus.value = 'unavailable'
    statusMessage.value = '数据服务暂时不可用，其他工作区功能仍可使用'
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<template>
  <div class="home-page" :aria-busy="loading">
    <section class="desk-head page-shell">
      <div>
        <p class="edition">INFOPULSE / PUBLIC SIGNAL DESK</p>
        <h1>今天的公开讨论，<br><em>先看信号，再做判断。</em></h1>
      </div>
      <div class="head-side">
        <span class="live-state" :class="{ offline: sourceStatus !== 'live' }"><i></i>{{ sourceStatus === 'live' ? '实时接入' : '来源暂不可用' }}</span>
        <button type="button" @click="router.push('/insight')"><el-icon><Search /></el-icon>分析一个话题</button>
      </div>
    </section>

    <main class="home-content page-shell">
      <section class="feature-grid">
        <article class="lead-story" @click="router.push('/hot-search')">
          <img src="@/assets/images/home-news.jpg" alt="阅读新闻与公开信息" />
          <div class="lead-shade"></div>
          <span class="scan-line"></span>
          <div class="lead-kicker"><i></i>跨来源信号第一位</div>
          <div class="lead-copy">
            <p>{{ lead?.category || '实时情报' }} · {{ lead ? formatHeat(Number(lead.heat || 0)) : '等待数据' }} 热度</p>
            <h2>{{ lead?.title || '正在接入今天值得关注的公开讨论' }}</h2>
            <button type="button">查看完整榜单<el-icon><ArrowRight /></el-icon></button>
          </div>
        </article>

        <aside class="ranking-panel">
          <header>
            <div><p>LIVE RANKING</p><h2>真实情报信号榜</h2></div>
            <button type="button" title="刷新热搜" :disabled="loading" @click="loadDashboard"><el-icon><Refresh /></el-icon></button>
          </header>
          <ol v-if="hotItems.length">
            <li v-for="(item, index) in hotItems.slice(0, 6)" :key="item.title" @click="router.push({ path: '/insight', query: { q: item.title } })">
              <span>{{ String(index + 1).padStart(2, '0') }}</span>
              <div><strong>{{ item.title }}</strong><small>{{ item.category || '热搜' }} · {{ formatHeat(Number(item.heat || 0)) }}</small></div>
              <em v-if="item.label">{{ item.label }}</em>
              <el-icon><ArrowUpRight /></el-icon>
            </li>
          </ol>
          <div v-else class="ranking-empty">
            <span class="loading-wave"><i></i><i></i><i></i><i></i></span>
            <strong>{{ loading ? '正在读取公开榜单' : '榜单暂时不可用' }}</strong>
            <p>{{ statusMessage }}</p>
          </div>
          <footer><router-link :to="sourceUrl">统一数据源<el-icon><TopRight /></el-icon></router-link><time>{{ updatedAt }}</time></footer>
        </aside>
      </section>

      <section class="signal-strip" aria-label="热榜摘要">
        <div><span>实时话题</span><strong>{{ hotItems.length || '—' }}</strong><small>当前公开信号</small></div>
        <div><span>最高热度</span><strong>{{ topHeat ? formatHeat(topHeat) : '—' }}</strong><small>榜首讨论强度</small></div>
        <div><span>话题覆盖</span><strong>{{ categoryCount || '—' }}</strong><small>当前分类数量</small></div>
        <div class="signal-note"><i></i><p>榜单只使用已同步的官方 API 与 RSS 内容；每条信号保留原始来源链接。</p></div>
      </section>

      <section class="workflow-section">
        <header><div><p class="eyebrow">CORE WORKFLOWS</p><h2>从一个信号开始工作</h2></div><p>三个工具共享公开来源和个人历史记录。</p></header>
        <div class="workflow-grid">
          <button v-for="item in workflows" :key="item.path" type="button" :class="item.tone" @click="router.push(item.path)">
            <span class="workflow-code">{{ item.code }}</span>
            <el-icon class="workflow-icon"><component :is="item.icon" /></el-icon>
            <div><h3>{{ item.title }}</h3><p>{{ item.description }}</p></div>
            <span class="workflow-action">{{ item.action }}<el-icon><ArrowRight /></el-icon></span>
          </button>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.home-page { min-height: calc(100vh - 72px); color: #16221f; background-color: #eef2f0; background-image: linear-gradient(rgba(24,52,45,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(24,52,45,.035) 1px, transparent 1px); background-size: 32px 32px; }
.desk-head { padding-top: 38px; padding-bottom: 26px; display: flex; align-items: flex-end; justify-content: space-between; border-bottom: 1px solid #c8d2ce; }
.edition { margin: 0 0 12px; color: #237f78; font: 750 10px/1.2 "Cascadia Code", monospace; letter-spacing: .12em; }
.desk-head h1 { margin: 0; font: 650 clamp(34px, 4vw, 58px)/1.06 Georgia, "Songti SC", serif; }.desk-head h1 em { color: #57716a; font-style: normal; font-weight: 400; }
.head-side { display: flex; align-items: center; gap: 18px; }.live-state { display: flex; align-items: center; gap: 8px; color: #4f6d65; font-size: 11px; }.live-state i { width: 7px; height: 7px; border-radius: 50%; background: #1fa674; box-shadow: 0 0 0 5px rgba(31,166,116,.1); animation: live 1.8s ease-in-out infinite; }.live-state.offline i { background: #dc625c; animation: none; }@keyframes live { 50% { opacity: .45; } }
.head-side button { min-height: 44px; padding: 0 17px; border: 1px solid #14231f; border-radius: 5px; display: inline-flex; align-items: center; gap: 8px; color: white; background: #14231f; cursor: pointer; transition: transform 160ms ease, background 160ms ease; }.head-side button:hover { transform: translateY(-2px); background: #237f78; }
.home-content { padding-top: 0; }.feature-grid { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(340px, .75fr); gap: 16px; }
.lead-story { position: relative; min-height: 430px; overflow: hidden; border-radius: 8px; color: white; background: #17221f; cursor: pointer; }.lead-story img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; transition: transform 700ms cubic-bezier(.2,.7,.2,1); }.lead-story:hover img { transform: scale(1.035); }.lead-shade { position: absolute; inset: 0; background: linear-gradient(90deg, rgba(8,20,17,.9), rgba(8,20,17,.4) 64%, rgba(8,20,17,.1)); }.scan-line { position: absolute; top: 0; bottom: 0; width: 1px; background: rgba(122,232,216,.55); box-shadow: 0 0 18px rgba(82,214,195,.8); animation: scan 7s linear infinite; }@keyframes scan { from { left: 0; } to { left: 100%; } }
.lead-kicker { position: absolute; left: 34px; top: 30px; display: flex; align-items: center; gap: 9px; color: #d7ebe6; font-size: 11px; }.lead-kicker i { width: 7px; height: 7px; border-radius: 50%; background: #ef6b63; box-shadow: 0 0 0 5px rgba(239,107,99,.16); }
.lead-copy { position: absolute; left: 34px; right: 34px; bottom: 34px; max-width: 760px; }.lead-copy > p { color: #9edbd0; font: 700 10px/1.2 "Cascadia Code", monospace; }.lead-copy h2 { margin: 12px 0 24px; font: 650 clamp(30px, 3.8vw, 54px)/1.12 Georgia, "Songti SC", serif; }.lead-copy button { min-height: 42px; padding: 0 15px; border: 1px solid rgba(255,255,255,.44); border-radius: 4px; display: inline-flex; align-items: center; gap: 8px; color: white; background: rgba(12,28,24,.34); backdrop-filter: blur(10px); cursor: pointer; }
.ranking-panel { min-height: 430px; padding: 20px 22px 14px; border: 1px solid #cad4d0; border-radius: 8px; background: rgba(255,255,255,.9); box-shadow: 0 18px 44px rgba(25,48,41,.08); }.ranking-panel > header { height: 54px; display: flex; align-items: flex-start; justify-content: space-between; border-bottom: 2px solid #17231f; }.ranking-panel header p { margin: 0; color: #237f78; font: 700 9px/1 monospace; letter-spacing: .1em; }.ranking-panel header h2 { margin: 5px 0 0; font-size: 18px; }.ranking-panel header button { width: 34px; height: 34px; border: 1px solid #d3dcd8; border-radius: 4px; color: #49645d; background: white; cursor: pointer; }.ranking-panel header button:hover .el-icon { transform: rotate(90deg); }.ranking-panel header .el-icon { transition: transform 220ms ease; }
.ranking-panel ol { margin: 0; padding: 0; list-style: none; }.ranking-panel li { min-height: 50px; display: grid; grid-template-columns: 28px 1fr auto 16px; gap: 9px; align-items: center; border-bottom: 1px solid #e4e9e7; cursor: pointer; }.ranking-panel li:hover { color: #167c73; }.ranking-panel li > span { color: #84958f; font: 700 10px/1 monospace; }.ranking-panel li:nth-child(-n+3) > span { color: #e25650; }.ranking-panel li div { min-width: 0; }.ranking-panel li strong, .ranking-panel li small { display: block; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }.ranking-panel li strong { font-size: 12px; }.ranking-panel li small { margin-top: 3px; color: #84958f; font-size: 9px; }.ranking-panel li em { padding: 2px 4px; border-radius: 3px; color: #c8433f; background: #fff0ee; font-size: 9px; font-style: normal; }.ranking-panel li > .el-icon { color: #a3b0ac; font-size: 12px; }
.ranking-panel > footer { min-height: 34px; padding-top: 10px; display: flex; justify-content: space-between; gap: 12px; color: #87958f; font-size: 9px; }.ranking-panel footer a { display: flex; align-items: center; gap: 3px; color: #237f78; }.ranking-empty { min-height: 300px; display: grid; align-content: center; justify-items: center; text-align: center; }.ranking-empty p { color: #7b8c86; font-size: 11px; }.loading-wave { display: flex; align-items: end; gap: 4px; height: 32px; }.loading-wave i { width: 4px; height: 12px; background: #38a89e; animation: wave 1s ease-in-out infinite; }.loading-wave i:nth-child(2) { height: 28px; animation-delay: .12s; }.loading-wave i:nth-child(3) { height: 20px; animation-delay: .24s; }.loading-wave i:nth-child(4) { height: 8px; animation-delay: .36s; }@keyframes wave { 50% { transform: scaleY(.45); } }
.signal-strip { min-height: 92px; margin-top: 16px; display: grid; grid-template-columns: repeat(3, minmax(130px, .55fr)) minmax(260px, 1.35fr); border: 1px solid #cad4d0; border-radius: 7px; background: rgba(255,255,255,.76); }.signal-strip > div { padding: 17px 20px; border-left: 1px solid #d8e0dc; }.signal-strip > div:first-child { border-left: 0; }.signal-strip span, .signal-strip small { display: block; color: #7a8d86; font-size: 9px; }.signal-strip strong { display: block; margin: 3px 0; font: 650 24px/1.1 Georgia, serif; }.signal-note { display: flex; align-items: center; gap: 12px; }.signal-note i { flex: 0 0 auto; width: 8px; height: 8px; border-radius: 50%; background: #e6af3f; }.signal-note p { margin: 0; color: #60766f; font-size: 11px; line-height: 1.65; }
.workflow-section { padding: 42px 0 6px; }.workflow-section > header { margin-bottom: 16px; display: flex; justify-content: space-between; align-items: end; }.workflow-section h2 { margin: 0; font: 650 30px/1.2 Georgia, "Songti SC", serif; }.workflow-section > header > p { color: #74867f; font-size: 11px; }.workflow-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }.workflow-grid > button { position: relative; min-height: 220px; padding: 22px; overflow: hidden; border: 1px solid #cad4d0; border-radius: 8px; display: grid; grid-template-columns: 1fr auto; align-content: space-between; color: #17231f; background: rgba(255,255,255,.84); text-align: left; cursor: pointer; transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease; }.workflow-grid > button:hover { transform: translateY(-4px); border-color: #7fa9a0; box-shadow: 0 18px 38px rgba(28,60,50,.1); }.workflow-grid > button::after { content: ''; position: absolute; left: 0; right: 0; top: 0; height: 3px; }.workflow-grid .cyan::after { background: #2b9b91; }.workflow-grid .coral::after { background: #e2675f; }.workflow-grid .gold::after { background: #d7a634; }.workflow-code { color: #8b9994; font: 700 10px/1 monospace; }.workflow-icon { font-size: 24px; color: #2d7d74; }.workflow-grid h3 { margin: 28px 0 8px; font-size: 21px; }.workflow-grid p { margin: 0; color: #657a73; font-size: 12px; line-height: 1.7; }.workflow-action { grid-column: 1 / -1; display: flex; align-items: center; justify-content: space-between; padding-top: 16px; border-top: 1px solid #e0e6e3; color: #294f47; font-size: 11px; font-weight: 700; }
@media (max-width: 980px) { .feature-grid { grid-template-columns: 1fr; }.ranking-panel { min-height: auto; }.workflow-grid { grid-template-columns: 1fr 1fr; }.signal-strip { grid-template-columns: repeat(3, 1fr); }.signal-note { grid-column: 1 / -1; border-top: 1px solid #d8e0dc; border-left: 0 !important; } }
@media (max-width: 680px) { .desk-head { align-items: flex-start; gap: 22px; flex-direction: column; }.desk-head h1 { font-size: 38px; }.head-side { width: 100%; justify-content: space-between; }.live-state { font-size: 10px; }.feature-grid { gap: 12px; }.lead-story { min-height: 370px; }.lead-copy, .lead-kicker { left: 22px; right: 22px; }.lead-copy h2 { font-size: 34px; }.ranking-panel { padding: 18px 16px 12px; }.signal-strip { grid-template-columns: 1fr 1fr; }.signal-strip > div:nth-child(3) { border-top: 1px solid #d8e0dc; border-left: 0; }.signal-note { grid-column: auto; border-left: 1px solid #d8e0dc !important; }.signal-note p { font-size: 10px; }.workflow-section > header > p { display: none; }.workflow-grid { grid-template-columns: 1fr; }.workflow-grid > button { min-height: 190px; } }
</style>
