<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { workflowApi } from '@/api/workflows'

const router = useRouter()
const loading = ref(false)
const items = ref<any[]>([])
const activeModule = ref<'all' | 'insight' | 'mouthpiece' | 'timeline'>('all')

const moduleMeta = {
  insight: { label: '热点洞察', code: 'SIGNAL', route: '/insight' },
  mouthpiece: { label: '表达文案', code: 'VOICE', route: '/mouthpiece' },
  timeline: { label: '事件脉络', code: 'ARCHIVE', route: '/timeline' },
} as const

const visibleItems = computed(() => activeModule.value === 'all' ? items.value : items.value.filter(item => item.module === activeModule.value))

function titleOf(item: any) {
  if (item.module === 'mouthpiece') return item.output_result?.title || item.input_params?.source_text?.slice(0, 30) || '未命名文案'
  return item.output_result?.topic || item.input_params?.keyword || item.input_params?.topic || '未命名记录'
}

function summaryOf(item: any) {
  if (item.module === 'mouthpiece') return item.output_result?.body || ''
  return item.output_result?.overview || item.output_result?.summary || ''
}

async function load() {
  loading.value = true
  try { items.value = (await workflowApi.getHistory()).items }
  finally { loading.value = false }
}
async function remove(id: string) {
  await ElMessageBox.confirm('删除后无法恢复，是否继续？', '删除报告', { type: 'warning' })
  await workflowApi.deleteHistory(id)
  items.value = items.value.filter(item => item.id !== id)
}
onMounted(load)
</script>

<template>
  <div class="history-page">
    <header class="history-head page-shell"><div><p class="eyebrow">PERSONAL INTELLIGENCE ARCHIVE</p><h1>我的内容档案</h1><p>洞察、表达与事件线索，按时间自动归档。</p></div><button type="button" @click="router.push('/insight')"><el-icon><Plus /></el-icon>新建洞察</button></header>
    <main class="archive-shell page-shell" :aria-busy="loading">
      <nav class="archive-tabs" aria-label="档案类型">
        <button v-for="tab in [{ key: 'all', label: '全部' }, { key: 'insight', label: '热点洞察' }, { key: 'mouthpiece', label: '表达文案' }, { key: 'timeline', label: '事件脉络' }]" :key="tab.key" type="button" :class="{ active: activeModule === tab.key }" @click="activeModule = tab.key as typeof activeModule">{{ tab.label }}</button>
        <span>{{ visibleItems.length }} RECORDS</span>
      </nav>
      <div v-if="visibleItems.length" class="archive-list">
        <article v-for="(item, index) in visibleItems" :key="item.id">
          <div class="record-index mono">{{ String(index + 1).padStart(3, '0') }}</div>
          <div class="record-type"><span>{{ moduleMeta[item.module as keyof typeof moduleMeta]?.code || 'REPORT' }}</span><strong>{{ moduleMeta[item.module as keyof typeof moduleMeta]?.label || item.module }}</strong></div>
          <div class="record-copy"><h2>{{ titleOf(item) }}</h2><p>{{ summaryOf(item) }}</p></div>
          <time>{{ new Date(item.created_at).toLocaleDateString('zh-CN') }}<small>{{ new Date(item.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}</small></time>
          <div class="record-actions"><button type="button" aria-label="继续创作" @click="router.push(moduleMeta[item.module as keyof typeof moduleMeta]?.route || '/insight')"><el-icon><ArrowRight /></el-icon></button><button type="button" aria-label="删除" @click="remove(item.id)"><el-icon><Delete /></el-icon></button></div>
        </article>
      </div>
      <div v-else class="empty-history"><el-icon><Files /></el-icon><h2>{{ loading ? '正在调取档案' : '这个分类还没有内容' }}</h2><p>完成热点洞察、表达创作或事件脉络后，内容会自动保存在这里。</p><button v-if="!loading" @click="router.push('/insight')">开始第一份分析</button></div>
    </main>
  </div>
</template>

<style scoped>
.history-page { min-height: calc(100vh - 64px); color: #241d17; background: #e9e4dc; }.history-head { display: flex; align-items: end; justify-content: space-between; border-bottom: 1px solid #b7aea3; }.history-head h1 { margin: 0; font: 800 44px/1.05 Georgia, "Songti SC", serif; }.history-head > div > p:last-child { margin: 10px 0 0; color: #74695f; }.history-head > button, .empty-history button { min-height: 40px; padding: 0 14px; border: 1px solid #30271f; border-radius: 2px; color: #f8f4ee; background: #30271f; display: flex; align-items: center; gap: 7px; cursor: pointer; }.archive-shell { padding-top: 22px; }.archive-tabs { min-height: 52px; padding: 0 16px; display: flex; align-items: center; gap: 6px; border: 1px solid #c4bbb0; background: #f4f0ea; }.archive-tabs button { flex: 0 0 auto; min-height: 30px; padding: 0 12px; border: 0; background: transparent; color: #756b62; white-space: nowrap; cursor: pointer; }.archive-tabs button.active { color: #fff; background: #9d3f32; }.archive-tabs > span { margin-left: auto; color: #8d8176; font: 700 9px/1 "Cascadia Code", monospace; }.archive-list { border: 1px solid #c4bbb0; border-top: 0; background: #f8f5f0; }.archive-list article { min-height: 116px; padding: 18px 16px; display: grid; grid-template-columns: 58px 110px minmax(260px, 1fr) 120px 80px; gap: 18px; align-items: center; border-top: 1px solid #d7cfc5; }.archive-list article:first-child { border-top: 0; }.record-index { color: #a99e92; font-size: 12px; }.record-type span, .record-type strong { display: block; }.record-type span { color: #9d3f32; font: 800 9px/1 "Cascadia Code", monospace; }.record-type strong { margin-top: 7px; font-size: 12px; }.record-copy { min-width: 0; }.record-copy h2 { margin: 0; overflow: hidden; font: 700 20px/1.3 Georgia, "Songti SC", serif; text-overflow: ellipsis; white-space: nowrap; }.record-copy p { margin: 8px 0 0; overflow: hidden; color: #756b62; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }.archive-list time { color: #62584f; font: 700 11px/1.3 "Cascadia Code", monospace; }.archive-list time small { display: block; margin-top: 6px; color: #9a8f84; }.record-actions { display: flex; }.record-actions button { width: 34px; height: 34px; border: 1px solid #cfc5ba; color: #74695f; background: transparent; cursor: pointer; }.record-actions button:hover { color: #fff; background: #9d3f32; }.empty-history { min-height: 480px; display: grid; place-items: center; align-content: center; text-align: center; }.empty-history > .el-icon { font-size: 58px; color: #a99e92; }.empty-history h2 { margin: 18px 0 5px; }.empty-history p { color: #756b62; }.empty-history button { margin-top: 12px; }
@media (max-width: 820px) { .history-head { align-items: flex-start; gap: 18px; }.archive-tabs { overflow-x: auto; }.archive-tabs > span { display: none; }.archive-list article { grid-template-columns: 42px 90px minmax(180px, 1fr) 68px; }.archive-list time { display: none; }.record-actions { grid-column: 4; grid-row: 1; } }
@media (max-width: 560px) { .history-head h1 { font-size: 34px; }.history-head > button { display: none; }.archive-list article { grid-template-columns: 36px 1fr 70px; gap: 10px; }.record-type { grid-column: 2; }.record-copy { grid-column: 1 / -1; grid-row: 2; }.record-actions { grid-column: 3; grid-row: 1; }.record-copy h2 { font-size: 18px; } }
</style>

<style scoped>
.history-page { color: #17231f; background: #eef2f0; }.history-head { position: relative; border-color: #becbc6; }.history-head::after { content: ''; position: absolute; left: 0; bottom: -1px; width: 92px; height: 3px; background: #167f76; }.history-head h1 { font: 650 44px/1.05 Georgia, "Songti SC", serif; }.history-head > div > p:last-child { color: #687c75; }.history-head > button, .empty-history button { border-color: #183129; border-radius: 5px; background: #183129; transition: transform 160ms ease, background 160ms ease; }.history-head > button:hover, .empty-history button:hover { transform: translateY(-2px); background: #167f76; }
.archive-tabs { overflow: hidden; border-color: #c4d0cb; border-radius: 7px 7px 0 0; background: rgba(255,255,255,.82); }.archive-tabs button { border-radius: 4px; color: #667a73; }.archive-tabs button.active { background: #167f76; }.archive-list { border-color: #c4d0cb; border-radius: 0 0 7px 7px; background: rgba(255,255,255,.86); box-shadow: 0 16px 36px rgba(26,54,45,.07); }.archive-list article { border-color: #dbe3df; transition: background 160ms ease, transform 160ms ease; }.archive-list article:hover { background: #f7faf8; transform: translateX(3px); }.record-type span { color: #c7524c; }.record-copy h2 { font-weight: 650; }.record-copy p, .empty-history p { color: #6d7f78; }.record-actions button { border-color: #c6d2cd; border-radius: 4px; }.record-actions button:hover { background: #167f76; }
</style>
