<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { analyzeInsight, type InsightResult } from '@/api/workflows'
import type { SSEConnection } from '@/utils/sse'

const route = useRoute()
const router = useRouter()
const keyword = ref('')
const analyzing = ref(false)
const progress = reactive({ message: '等待输入话题', percent: 0 })
const result = ref<InsightResult | null>(null)
const error = ref('')
let connection: SSEConnection | null = null

const sentimentItems = computed(() => result.value ? [
  { label: '正向', value: result.value.sentiment.positive, color: '#18a874' },
  { label: '中性', value: result.value.sentiment.neutral, color: '#f1b542' },
  { label: '负向', value: result.value.sentiment.negative, color: '#e34f54' },
] : [])
const dominantSentiment = computed(() => sentimentItems.value.slice().sort((a, b) => b.value - a.value)[0])

function run() {
  if (keyword.value.trim().length < 2) return ElMessage.warning('请输入至少 2 个字的话题')
  connection?.close()
  analyzing.value = true
  result.value = null
  error.value = ''
  progress.percent = 8
  progress.message = '正在建立话题样本集'
  connection = analyzeInsight({ keyword: keyword.value.trim(), platforms: ['weibo', 'bilibili', 'tieba'], max_items: 36 }, {
    onProgress: (data) => { progress.message = data.message || progress.message; progress.percent = data.percent || progress.percent },
    onResult: (data) => { result.value = data; analyzing.value = false },
    onError: (message) => { error.value = message; analyzing.value = false },
    onTimeout: () => { error.value = '分析时间较长，请稍后重试'; analyzing.value = false },
  })
}

onMounted(() => { if (typeof route.query.q === 'string') keyword.value = route.query.q })
onBeforeUnmount(() => connection?.close())
</script>

<template>
  <div class="insight-page">
    <section class="query-rail">
      <div class="rail-top">
        <p>INVESTIGATION DESK</p>
        <h1>热点<br>洞察</h1>
        <span>公开讨论样本 · 三端交叉观察</span>
      </div>
      <div class="source-list">
        <div><i class="weibo"></i><span>微博</span><small>公共讨论</small></div>
        <div><i class="bilibili"></i><span>B站</span><small>视频社区</small></div>
        <div><i class="tieba"></i><span>贴吧</span><small>兴趣论坛</small></div>
      </div>
      <div class="rail-note">报告只呈现公开来源，不将网友猜测当作已证实事实。</div>
    </section>

    <main class="investigation-board">
      <section class="search-section">
        <p class="eyebrow">NEW INVESTIGATION</p>
        <div class="search-line">
          <input v-model="keyword" placeholder="输入人物、事件或正在发酵的话题" maxlength="80" @keyup.enter="run" />
          <button type="button" :disabled="analyzing" @click="run"><el-icon><Search /></el-icon>{{ analyzing ? '分析中' : '生成洞察' }}</button>
        </div>
        <div class="examples"><span>示例</span><button v-for="item in ['演唱会退票争议', '新手机发布', '热门影视结局']" :key="item" @click="keyword = item">{{ item }}</button></div>
      </section>

      <section v-if="analyzing" class="analysis-progress">
        <div class="scan-grid"><i></i><i></i><i></i><i></i><span></span></div>
        <div><p>{{ progress.message }}</p><strong>{{ progress.percent }}%</strong><el-progress :percentage="progress.percent" :show-text="false" /></div>
      </section>
      <section v-else-if="error" class="error-panel"><el-icon><Warning /></el-icon><div><strong>这次没有形成有效报告</strong><p>{{ error }}</p></div><button @click="run">重新分析</button></section>

      <template v-if="result">
        <section class="report-head">
          <div><p class="eyebrow">REPORT / {{ result.topic }}</p><h2>{{ result.overview }}</h2></div>
          <div class="confidence"><span>{{ result.confidence }}</span><small>可信度</small></div>
        </section>

        <section class="report-grid">
          <article class="sentiment-panel">
            <header><strong>情绪结构</strong><small>{{ result.volume }} 条有效样本</small></header>
            <div class="donut" :style="{ '--positive': `${result.sentiment.positive * 3.6}deg`, '--neutral': `${(result.sentiment.positive + result.sentiment.neutral) * 3.6}deg` }">
              <div><strong>{{ dominantSentiment?.value }}%</strong><span>{{ dominantSentiment?.label }}占主导</span></div>
            </div>
            <ul><li v-for="item in sentimentItems" :key="item.label"><i :style="{ background: item.color }"></i><span>{{ item.label }}</span><strong>{{ item.value }}%</strong></li></ul>
          </article>

          <article class="source-panel">
            <header><strong>来源覆盖</strong><small>采集状态</small></header>
            <div v-for="source in result.sources" :key="source.platform" class="source-row">
              <span>{{ { weibo: '微博', bilibili: 'B站', tieba: '贴吧' }[source.platform] || source.platform }}</span>
              <div><i :style="{ width: `${Math.min(100, source.count * 8)}%` }"></i></div>
              <strong>{{ source.count }}</strong>
            </div>
          </article>

          <article class="points-panel">
            <header><strong>关键观点</strong><small>AI 聚类</small></header>
            <ol><li v-for="(point, index) in result.key_points" :key="point.label"><span class="mono">{{ String(index + 1).padStart(2, '0') }}</span><div><strong>{{ point.label }}</strong><p>{{ point.detail }}</p></div><em :class="point.stance">{{ point.stance }}</em></li></ol>
          </article>
        </section>

        <section class="opinions-section">
          <div class="section-heading"><div><p class="eyebrow">SOURCE VOICES</p><h2>代表性原文</h2></div><span>点击卡片打开原始来源</span></div>
          <div class="opinion-grid"><a v-for="item in result.representative_opinions" :key="item.url + item.content" :href="item.url || undefined" target="_blank" rel="noreferrer" class="opinion-card"><span>{{ item.platform }}</span><p>{{ item.content }}</p><footer><em :class="item.stance">{{ item.stance }}</em><el-icon><TopRight /></el-icon></footer></a></div>
        </section>

        <section class="risk-strip"><el-icon><InfoFilled /></el-icon><div><strong>阅读提醒</strong><p>{{ result.risks.join('；') }}</p></div></section>
        <section class="next-actions"><div><p class="eyebrow">CONTINUE WORKING</p><h2>继续处理「{{ result.topic }}」</h2></div><button @click="router.push({ path: '/timeline', query: { q: result.topic } })"><el-icon><Clock /></el-icon>建立事件脉络</button><button @click="router.push({ path: '/mouthpiece', query: { q: result.overview } })"><el-icon><EditPen /></el-icon>整理表达文案</button></section>
      </template>

      <section v-else-if="!analyzing && !error" class="empty-board">
        <div class="coordinate mono">A-01 / READY</div><div class="empty-wave"><i></i><i></i><i></i><i></i><i></i></div><h2>输入一个正在发酵的话题</h2><p>系统会自动完成多端采集、情绪识别、观点聚类和来源回溯。</p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.insight-page { min-height: calc(100vh - 64px); display: grid; grid-template-columns: 260px 1fr; background: #f1f4f8; }
.query-rail { position: sticky; top: 64px; align-self: start; height: calc(100vh - 64px); padding: 34px 28px; display: flex; flex-direction: column; color: white; background: #111b2b; overflow: hidden; }
.query-rail::after { content: ''; position: absolute; width: 280px; height: 280px; left: -130px; bottom: 80px; border: 1px solid rgba(91,164,255,.25); border-radius: 50%; box-shadow: 0 0 0 38px rgba(91,164,255,.06), 0 0 0 76px rgba(91,164,255,.035); }
.rail-top { position: relative; z-index: 1; }.rail-top p { color: #73b4ff; font: 700 10px/1.2 "Cascadia Code", monospace; }.rail-top h1 { margin: 20px 0 14px; font-size: 52px; line-height: .95; }.rail-top span { color: #8d9aae; font-size: 11px; }
.source-list { position: relative; z-index: 1; margin-top: 70px; border-top: 1px solid #29384d; }.source-list div { min-height: 64px; display: grid; grid-template-columns: 14px 1fr auto; align-items: center; gap: 9px; border-bottom: 1px solid #29384d; }.source-list i { width: 8px; height: 8px; border-radius: 50%; }.source-list .weibo { background: #ef4444; }.source-list .bilibili { background: #55bde9; }.source-list .tieba { background: #f5b942; }.source-list span { font-size: 13px; }.source-list small { color: #718096; font-size: 10px; }
.rail-note { position: relative; z-index: 1; margin-top: auto; padding-top: 20px; color: #7f8da2; font-size: 11px; border-top: 1px solid #29384d; }
.investigation-board { width: min(1180px, calc(100% - 48px)); margin: 0 auto; padding: 36px 0 64px; }
.search-section { padding-bottom: 28px; border-bottom: 1px solid #ccd5df; }.search-line { display: grid; grid-template-columns: 1fr auto; border-bottom: 3px solid #101828; }.search-line input { min-width: 0; padding: 12px 2px 16px; border: 0; outline: 0; background: transparent; color: #101828; font-size: clamp(22px, 3vw, 38px); font-weight: 750; }.search-line button { margin-bottom: 8px; min-width: 132px; padding: 0 18px; border: 0; border-radius: 4px; background: #1677ff; color: white; display: flex; align-items: center; justify-content: center; gap: 7px; cursor: pointer; }.search-line button:disabled { opacity: .55; }.examples { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; color: #98a2b3; font-size: 11px; }.examples button { padding: 5px 9px; border: 1px solid #d0d5dd; border-radius: 3px; background: white; color: #536174; cursor: pointer; }
.analysis-progress, .error-panel { margin-top: 24px; min-height: 180px; padding: 28px; border: 1px solid #d0d5dd; background: white; display: grid; grid-template-columns: 180px 1fr; gap: 32px; align-items: center; }.scan-grid { position: relative; height: 120px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; }.scan-grid i { background: #eef4fb; border: 1px solid #d8e4f2; }.scan-grid span { position: absolute; left: 0; right: 0; height: 2px; background: #1677ff; box-shadow: 0 0 14px #1677ff; animation: scan 1.8s ease-in-out infinite; }@keyframes scan { 0%,100% { top: 0; } 50% { top: 100%; } }.analysis-progress p { margin: 0 0 10px; color: #536174; }.analysis-progress strong { display: block; margin-bottom: 12px; font-size: 34px; }.error-panel { grid-template-columns: 42px 1fr auto; }.error-panel > .el-icon { color: #e5484d; font-size: 32px; }.error-panel p { margin: 4px 0 0; color: #667085; }.error-panel button { padding: 9px 14px; border: 1px solid #d0d5dd; background: white; cursor: pointer; }
.report-head { padding: 32px 0; display: grid; grid-template-columns: 1fr 110px; gap: 30px; align-items: end; }.report-head h2 { margin: 0; max-width: 900px; font: 700 clamp(23px, 3vw, 36px)/1.4 Georgia, "Songti SC", serif; }.confidence { height: 92px; border-left: 1px solid #ccd5df; display: flex; flex-direction: column; align-items: flex-end; justify-content: end; }.confidence span { font: 800 42px/1 "Cascadia Code", monospace; color: #1677ff; }.confidence small { margin-top: 6px; color: #667085; }
.report-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }.report-grid article { padding: 22px; border: 1px solid #d0d5dd; background: white; }.report-grid article > header { display: flex; justify-content: space-between; border-bottom: 1px solid #e4e7ec; padding-bottom: 12px; }.report-grid header small { color: #98a2b3; }.sentiment-panel { display: grid; grid-template-columns: 1fr 1fr; }.sentiment-panel header { grid-column: 1/-1; }.donut { width: 160px; aspect-ratio: 1; margin: 26px auto 12px; border-radius: 50%; background: conic-gradient(#18a874 0 var(--positive), #f1b542 var(--positive) var(--neutral), #e34f54 var(--neutral) 360deg); display: grid; place-items: center; }.donut::before { content: ''; grid-area: 1/1; width: 112px; height: 112px; border-radius: 50%; background: white; }.donut div { grid-area: 1/1; z-index: 1; text-align: center; }.donut strong, .donut span { display: block; }.donut strong { font-size: 30px; }.donut span { color: #667085; font-size: 10px; }.sentiment-panel ul { margin: 28px 0 0; padding: 0; list-style: none; }.sentiment-panel li { padding: 9px 0; display: grid; grid-template-columns: 10px 1fr auto; align-items: center; gap: 7px; border-bottom: 1px solid #edf0f3; }.sentiment-panel li i { width: 7px; height: 7px; border-radius: 50%; }
.source-row { padding: 21px 0; display: grid; grid-template-columns: 54px 1fr 30px; align-items: center; gap: 12px; }.source-row > div { height: 7px; background: #edf0f3; }.source-row > div i { display: block; height: 100%; background: #1677ff; }.source-row strong { text-align: right; font-family: "Cascadia Code", monospace; }
.points-panel { grid-column: 1/-1; }.points-panel ol { margin: 0; padding: 0; list-style: none; }.points-panel li { padding: 18px 0; display: grid; grid-template-columns: 36px 1fr auto; gap: 16px; border-bottom: 1px solid #e4e7ec; }.points-panel li > span { color: #98a2b3; }.points-panel h3, .points-panel p { margin: 0; }.points-panel p { margin-top: 5px; color: #667085; }.points-panel em, .opinion-card em { align-self: start; padding: 4px 7px; border-radius: 3px; background: #f2f4f7; color: #667085; font-style: normal; font-size: 10px; }.points-panel em.negative, .opinion-card em.negative { background: #feecec; color: #c43237; }.points-panel em.positive, .opinion-card em.positive { background: #e9f8f2; color: #087a52; }
.opinions-section { margin-top: 38px; }.section-heading { margin-bottom: 14px; display: flex; justify-content: space-between; align-items: flex-end; }.section-heading h2 { margin: 0; }.section-heading > span { color: #98a2b3; font-size: 11px; }.opinion-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }.opinion-card { min-height: 180px; padding: 18px; display: flex; flex-direction: column; border: 1px solid #d0d5dd; background: white; transition: transform 160ms ease, border-color 160ms ease; }.opinion-card:hover { transform: translateY(-3px); border-color: #1677ff; }.opinion-card > span { color: #1677ff; font: 700 10px/1 "Cascadia Code", monospace; text-transform: uppercase; }.opinion-card p { color: #344054; font-size: 13px; line-height: 1.7; }.opinion-card footer { margin-top: auto; display: flex; justify-content: space-between; align-items: center; }
.risk-strip { margin-top: 16px; padding: 16px 18px; display: grid; grid-template-columns: 24px 1fr; gap: 10px; background: #fff8e7; border: 1px solid #efd491; }.risk-strip p { margin: 2px 0 0; color: #76612f; }
.empty-board { min-height: 480px; position: relative; display: grid; place-items: center; align-content: center; text-align: center; border-bottom: 1px solid #ccd5df; }.coordinate { position: absolute; left: 0; top: 30px; color: #98a2b3; font-size: 10px; }.empty-wave { height: 80px; display: flex; align-items: center; gap: 7px; }.empty-wave i { width: 8px; background: #bdd8fb; animation: waveform 1.2s ease-in-out infinite; }.empty-wave i:nth-child(1), .empty-wave i:nth-child(5) { height: 18px; }.empty-wave i:nth-child(2), .empty-wave i:nth-child(4) { height: 42px; animation-delay: .15s; }.empty-wave i:nth-child(3) { height: 70px; animation-delay: .3s; }@keyframes waveform { 50% { transform: scaleY(.4); background: #1677ff; } }.empty-board h2 { margin: 18px 0 6px; font-size: 28px; }.empty-board p { color: #667085; }
@media (max-width: 960px) { .insight-page { grid-template-columns: 1fr; }.query-rail { position: relative; top: 0; height: auto; padding: 22px; }.rail-top h1 { font-size: 34px; }.source-list { margin-top: 24px; display: grid; grid-template-columns: repeat(3,1fr); }.source-list div { border-top: 1px solid #29384d; }.rail-note { display: none; }.report-grid { grid-template-columns: 1fr; }.points-panel { grid-column: auto; }.opinion-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 620px) { .investigation-board { width: calc(100% - 24px); }.search-line { grid-template-columns: 1fr; }.search-line button { min-height: 44px; margin: 0 0 8px; }.report-head { grid-template-columns: 1fr; }.confidence { display: none; }.sentiment-panel { grid-template-columns: 1fr; }.opinion-grid { grid-template-columns: 1fr; }.analysis-progress { grid-template-columns: 1fr; }.scan-grid { display: none; } }
</style>

<style scoped>
.next-actions { margin-top: 18px; padding: 20px 22px; border: 1px solid #cbd5df; display: grid; grid-template-columns: 1fr auto auto; gap: 10px; align-items: center; background: #fff; }.next-actions h2 { margin: 0; font-size: 18px; }.next-actions button { min-height: 40px; padding: 0 13px; border: 1px solid #b9c6d3; border-radius: 4px; display: flex; align-items: center; gap: 7px; color: #30455b; background: #f8fafc; cursor: pointer; }.next-actions button:hover { border-color: #1677ff; color: #1677ff; }
@media (max-width: 720px) { .next-actions { grid-template-columns: 1fr 1fr; }.next-actions > div { grid-column: 1 / -1; }.next-actions button { justify-content: center; } }
</style>

<style scoped>
.insight-page { background: #eef2f0; }
.query-rail { background: #14231f; }
.query-rail::after { left: 0; right: 0; bottom: 72px; width: auto; height: 240px; border: 0; border-radius: 0; box-shadow: none; background-image: linear-gradient(rgba(103,180,169,.09) 1px, transparent 1px), linear-gradient(90deg, rgba(103,180,169,.09) 1px, transparent 1px); background-size: 28px 28px; mask-image: linear-gradient(transparent, #000 32%, transparent); }
.rail-top p { color: #72cbbf; letter-spacing: .12em; }.rail-top h1 { font: 650 48px/.98 Georgia, "Songti SC", serif; }.rail-top span, .rail-note { color: #8ca099; }
.source-list, .source-list div, .rail-note { border-color: #2d433c; }.source-list small { color: #779087; }
.investigation-board { width: min(1120px, calc(100% - 48px)); }
.search-section { border-color: #c8d3cf; }.search-line { border-color: #17251f; }.search-line button { border-radius: 5px; background: #167f76; transition: transform 160ms ease, background 160ms ease; }.search-line button:hover { transform: translateY(-2px); background: #116a63; }.examples button { border-color: #ced9d4; border-radius: 4px; color: #536a63; transition: border-color 160ms ease, color 160ms ease; }.examples button:hover { border-color: #258d83; color: #167f76; }
.analysis-progress, .error-panel, .report-grid article, .opinion-card { border-color: #ced8d4; border-radius: 7px; box-shadow: 0 12px 30px rgba(25,54,45,.055); }.scan-grid i { border-color: #d5e3de; background: #edf4f1; }.scan-grid span { background: #2b968c; box-shadow: 0 0 14px #2b968c; }.confidence span, .opinion-card > span { color: #167f76; }.source-row > div i { background: #218a80; }.opinion-card:hover { border-color: #258d83; box-shadow: 0 16px 34px rgba(25,54,45,.1); }
.empty-board { isolation: isolate; border-color: #c8d3cf; }.empty-board::before { content: ''; position: absolute; inset: 50px 0 0; z-index: -1; background: linear-gradient(rgba(238,242,240,.84), rgba(238,242,240,.94)), url('../../assets/images/auth-newsroom.jpg') center/cover; opacity: .72; }.empty-wave i { background: #abd9d1; }.empty-board h2 { font: 650 29px/1.2 Georgia, "Songti SC", serif; }
@media (max-width: 960px) { .query-rail::after { display: none; }.investigation-board { width: min(100% - 32px, 1120px); } }
</style>
