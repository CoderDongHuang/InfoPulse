<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { workflowApi } from '@/api/workflows'

const topic = ref('')
const route = useRoute()
const loading = ref(false)
const result = ref<any>(null)

async function build() {
  if (topic.value.trim().length < 2) return ElMessage.warning('请输入事件名称')
  loading.value = true
  try { result.value = await workflowApi.buildTimeline({ topic: topic.value.trim(), platforms: ['weibo', 'bilibili', 'tieba'], max_items: 42 }) }
  finally { loading.value = false }
}

function exportMarkdown() {
  if (!result.value) return
  const lines = [`# ${result.value.topic}`, '', result.value.summary, '', ...result.value.nodes.flatMap((node: any) => [`## ${node.time} · ${node.title}`, node.detail, node.url ? `[来源](${node.url})` : '', ''])]
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `${result.value.topic}-事件脉络.md`; link.click(); URL.revokeObjectURL(link.href)
}
onMounted(() => { if (typeof route.query.q === 'string') topic.value = route.query.q })
</script>

<template>
  <div class="archive-page">
    <header class="archive-head page-shell">
      <div class="folder-tab">CASE FILE / 03</div>
      <div class="archive-title"><div><p>EVENT ARCHIVE</p><h1>事件脉络</h1></div><p>把公开信息按时间、来源和可信度重新排列。</p></div>
      <div class="topic-entry"><input v-model="topic" maxlength="100" placeholder="输入事件名称" @keyup.enter="build"><button type="button" :disabled="loading" @click="build"><el-icon><Collection /></el-icon>{{ loading ? '整理中' : '建立档案' }}</button></div>
    </header>

    <main class="archive-body page-shell" v-loading="loading">
      <template v-if="result">
        <section class="case-summary">
          <div class="case-number mono">CASE<br>{{ String(result.nodes.length).padStart(3, '0') }}</div>
          <div><p class="eyebrow">{{ result.topic }}</p><h2>{{ result.summary }}</h2></div>
          <button type="button" @click="exportMarkdown"><el-icon><Download /></el-icon>导出 Markdown</button>
        </section>

        <section class="timeline-rail">
          <article v-for="(node, index) in result.nodes" :key="`${node.time}-${index}`" class="timeline-node">
            <div class="node-date"><span>{{ node.time }}</span><small>可信度 {{ node.confidence }}%</small></div>
            <div class="node-pin"><i></i></div>
            <div class="node-content">
              <span class="source-stamp">{{ node.source }}</span><h3>{{ node.title }}</h3><p>{{ node.detail }}</p>
              <a v-if="node.url" :href="node.url" target="_blank" rel="noreferrer">核对原始来源<el-icon><TopRight /></el-icon></a>
            </div>
          </article>
        </section>

        <section class="unknowns"><header><el-icon><QuestionFilled /></el-icon><strong>仍待核验</strong></header><ul><li v-for="item in result.unknowns" :key="item">{{ item }}</li></ul></section>
      </template>

      <section v-else class="archive-empty">
        <div class="empty-folder"><i></i><span>01</span></div>
        <div><h2>为一个热点建立可回溯档案</h2><p>系统会从微博、B站和贴吧公开讨论中提取时间线索，并标注仍待核验的信息。</p></div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.archive-page { min-height: calc(100vh - 64px); color: #2a2824; background-color: #eeeae1; background-image: linear-gradient(rgba(66,58,44,.04) 1px, transparent 1px), linear-gradient(90deg, rgba(66,58,44,.04) 1px, transparent 1px); background-size: 24px 24px; }
.archive-head { padding-top: 34px; padding-bottom: 26px; border-bottom: 1px solid #b8b09f; }.folder-tab { width: fit-content; padding: 8px 14px; color: #f7f2e8; background: #7d3e37; font: 800 10px/1 "Cascadia Code", monospace; }.archive-title { margin-top: 22px; display: flex; justify-content: space-between; align-items: end; }.archive-title p { margin: 0; color: #766f63; }.archive-title > div p { font: 800 10px/1 "Cascadia Code", monospace; }.archive-title h1 { margin: 8px 0 0; font: 800 clamp(38px, 5vw, 68px)/1 Georgia, "Songti SC", serif; }.archive-title > p { max-width: 340px; }
.topic-entry { margin-top: 24px; display: grid; grid-template-columns: 1fr auto; border: 1px solid #a79d8b; background: rgba(255,253,248,.62); }.topic-entry input { min-height: 54px; padding: 0 18px; border: 0; outline: 0; background: transparent; font-size: 18px; }.topic-entry button { min-width: 140px; border: 0; background: #2f3a34; color: white; display: flex; align-items: center; justify-content: center; gap: 8px; cursor: pointer; }
.archive-body { padding-top: 30px; }.case-summary { padding: 24px; display: grid; grid-template-columns: 80px 1fr auto; gap: 24px; align-items: center; border: 1px solid #b8b09f; background: rgba(255,253,248,.76); }.case-number { padding-right: 20px; border-right: 1px solid #b8b09f; color: #7d3e37; font-size: 18px; }.case-summary h2 { margin: 0; font: 700 24px/1.45 Georgia, "Songti SC", serif; }.case-summary button { padding: 9px 12px; border: 1px solid #817866; background: transparent; display: flex; gap: 7px; align-items: center; cursor: pointer; }
.timeline-rail { position: relative; margin: 40px 0; }.timeline-rail::before { content: ''; position: absolute; left: 218px; top: 12px; bottom: 12px; width: 2px; background: #827864; }.timeline-node { display: grid; grid-template-columns: 190px 56px 1fr; min-height: 170px; }.node-date { padding-top: 4px; text-align: right; }.node-date span, .node-date small { display: block; }.node-date span { font-weight: 800; }.node-date small { margin-top: 7px; color: #8b8376; font-size: 10px; }.node-pin { position: relative; display: flex; justify-content: center; }.node-pin i { position: relative; z-index: 1; width: 14px; height: 14px; margin-top: 4px; border: 3px solid #eeeae1; border-radius: 50%; background: #7d3e37; box-shadow: 0 0 0 1px #7d3e37; }.node-content { margin-bottom: 22px; padding: 20px 22px; border: 1px solid #b8b09f; background: rgba(255,253,248,.8); box-shadow: 5px 5px 0 rgba(101,91,73,.08); }.source-stamp { color: #7d3e37; font: 800 10px/1 "Cascadia Code", monospace; text-transform: uppercase; }.node-content h3 { margin: 10px 0 8px; font-size: 20px; }.node-content p { margin: 0; color: #655f56; line-height: 1.8; }.node-content a { margin-top: 14px; display: inline-flex; align-items: center; gap: 5px; color: #7d3e37; font-size: 11px; font-weight: 700; }
.unknowns { margin-left: 246px; padding: 20px; border: 1px dashed #9a4d44; background: rgba(255,244,236,.72); }.unknowns header { display: flex; align-items: center; gap: 7px; color: #7d3e37; }.unknowns ul { margin: 10px 0 0; padding-left: 20px; color: #655f56; }
.archive-empty { min-height: 460px; display: grid; grid-template-columns: 180px minmax(0, 520px); justify-content: center; align-items: center; gap: 42px; }.empty-folder { position: relative; width: 170px; height: 125px; border: 1px solid #9e9584; background: #dad2c3; transform: rotate(-3deg); box-shadow: 8px 9px 0 rgba(86,77,63,.12); }.empty-folder i { position: absolute; left: 12px; top: -22px; width: 74px; height: 22px; background: #dad2c3; border: 1px solid #9e9584; border-bottom: 0; }.empty-folder span { position: absolute; right: 16px; bottom: 12px; color: #7d3e37; font: 800 24px/1 "Cascadia Code", monospace; }.archive-empty h2 { margin: 0; font: 800 30px/1.2 Georgia, "Songti SC", serif; }.archive-empty p { color: #766f63; }
@media (max-width: 760px) { .archive-title { align-items: flex-start; gap: 15px; flex-direction: column; }.case-summary { grid-template-columns: 1fr; }.case-number { display: none; }.timeline-rail::before { left: 8px; }.timeline-node { grid-template-columns: 22px 1fr; }.node-date { grid-column: 2; text-align: left; margin-bottom: 9px; }.node-pin { grid-column: 1; grid-row: 1 / span 2; }.node-content { grid-column: 2; }.unknowns { margin-left: 22px; }.archive-empty { grid-template-columns: 1fr; text-align: center; }.empty-folder { margin: 0 auto; } }
</style>

<style scoped>
.archive-page { color: #1c2d27; background-color: #eef2f0; background-image: linear-gradient(rgba(29,66,54,.04) 1px, transparent 1px), linear-gradient(90deg, rgba(29,66,54,.04) 1px, transparent 1px); background-size: 28px 28px; }
.archive-head { border-color: #bdcbc6; }.folder-tab { border-radius: 3px; background: #167f76; }.archive-title p { color: #687c75; }.archive-title h1 { font: 650 clamp(38px, 5vw, 64px)/1 Georgia, "Songti SC", serif; }.topic-entry { overflow: hidden; border-color: #9eb2aa; border-radius: 6px; background: rgba(255,255,255,.88); box-shadow: 0 12px 30px rgba(28,61,51,.06); }.topic-entry button { background: #183129; transition: background 160ms ease; }.topic-entry button:hover { background: #167f76; }
.case-summary { border-color: #c0ccc7; border-radius: 7px; background: rgba(255,255,255,.88); box-shadow: 0 12px 30px rgba(28,61,51,.06); }.case-number, .source-stamp, .node-content a { color: #b64f49; }.case-summary h2 { font-weight: 600; }.case-summary button { border-color: #8ca097; border-radius: 4px; }
.timeline-rail::before { background: #8ca097; }.node-pin i { border-color: #eef2f0; background: #d95c55; box-shadow: 0 0 0 1px #d95c55; }.node-content { border-color: #c4cfca; border-radius: 6px; background: rgba(255,255,255,.9); box-shadow: 0 10px 24px rgba(27,55,47,.06); transition: transform 160ms ease, box-shadow 160ms ease; }.node-content:hover { transform: translateX(4px); box-shadow: 0 14px 30px rgba(27,55,47,.1); }.node-content p, .archive-empty p { color: #64776f; }.unknowns { border-color: #d07973; border-radius: 6px; background: rgba(255,245,241,.84); }.unknowns header { color: #aa4842; }
.empty-folder { border-color: #93a69e; background: #d2ddd8; box-shadow: 8px 9px 0 rgba(45,74,64,.1); }.empty-folder i { border-color: #93a69e; background: #d2ddd8; }.empty-folder span { color: #b64f49; }.archive-empty h2 { font-weight: 650; }
</style>
