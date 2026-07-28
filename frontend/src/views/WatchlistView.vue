<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useWatchlistStore } from '@/stores/watchlist'
import EmptyState from '@/components/common/EmptyState.vue'

const router = useRouter()
const watchlist = useWatchlistStore()

function formatDate(value: string) {
  return new Date(value).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="watch-page">
    <header class="watch-head page-shell">
      <div><p class="eyebrow">TOPIC WATCHLIST</p><h1>关注话题</h1><p>先收下值得继续观察的信号，再决定做洞察还是梳理脉络。</p></div>
      <button type="button" @click="router.push('/hot-search')"><el-icon><TrendCharts /></el-icon>浏览实时热搜</button>
    </header>
    <main class="page-shell watch-body">
      <div v-if="watchlist.items.length" class="topic-list">
        <article v-for="(item, index) in watchlist.items" :key="item.title">
          <span class="index mono">{{ String(index + 1).padStart(2, '0') }}</span>
          <div class="topic-copy"><span>{{ item.category }}</span><h2>{{ item.title }}</h2><small>关注于 {{ formatDate(item.addedAt) }}</small></div>
          <div class="topic-actions">
            <button title="生成洞察" @click="router.push({ path: '/insight', query: { q: item.title } })"><el-icon><DataAnalysis /></el-icon><span>洞察</span></button>
            <button title="建立事件脉络" @click="router.push({ path: '/timeline', query: { q: item.title } })"><el-icon><Clock /></el-icon><span>脉络</span></button>
            <a v-if="item.sourceUrl" :href="item.sourceUrl" target="_blank" rel="noreferrer" title="打开来源"><el-icon><TopRight /></el-icon></a>
            <button class="remove" title="取消关注" @click="watchlist.remove(item.title)"><el-icon><Delete /></el-icon></button>
          </div>
        </article>
      </div>
      <EmptyState v-else title="还没有关注任何话题" description="在数据看板中关注话题后，会集中保存在这里。" action-label="查看当前信号" icon="CollectionTag" @action="router.push('/hot-search')" />
    </main>
  </div>
</template>

<style scoped>
.watch-page { min-height: 100vh; background: #f2f5f3; }.watch-head { display: flex; align-items: end; justify-content: space-between; border-bottom: 1px solid #cbd5d1; }.watch-head h1 { margin: 0; font: 650 44px/1.1 Georgia, "Songti SC", serif; }.watch-head p:last-child { margin: 10px 0 0; color: #667a73; }.watch-head > button, .empty-watch button { min-height: 42px; padding: 0 15px; border: 0; border-radius: 5px; display: flex; align-items: center; gap: 7px; color: white; background: #183129; cursor: pointer; }.watch-body { padding-top: 22px; }.topic-list { border-top: 2px solid #183129; }.topic-list article { min-height: 118px; padding: 20px 10px; display: grid; grid-template-columns: 52px minmax(0, 1fr) auto; gap: 18px; align-items: center; border-bottom: 1px solid #d6dfdb; }.index { color: #93a29d; }.topic-copy > span { color: #167f76; font-size: 10px; font-weight: 800; }.topic-copy h2 { margin: 5px 0; font-size: 21px; }.topic-copy small { color: #8a9994; }.topic-actions { display: flex; gap: 6px; }.topic-actions button, .topic-actions a { min-width: 38px; height: 38px; padding: 0 11px; border: 1px solid #c6d1cd; border-radius: 4px; display: inline-flex; align-items: center; justify-content: center; gap: 6px; color: #526a62; background: white; cursor: pointer; }.topic-actions .remove:hover { color: #c94f49; }.empty-watch { min-height: 470px; display: grid; justify-items: center; align-content: center; text-align: center; }.empty-watch > span { width: 72px; height: 72px; border-radius: 50%; display: grid; place-items: center; color: #167f76; background: #deece8; font-size: 30px; }.empty-watch h2 { margin: 18px 0 4px; }.empty-watch p { color: #71837d; }.empty-watch button { margin-top: 12px; }
@media (max-width: 680px) { .watch-head { align-items: flex-start; gap: 20px; flex-direction: column; }.topic-list article { grid-template-columns: 34px 1fr; }.topic-actions { grid-column: 2; flex-wrap: wrap; }.topic-actions button span { display: none; } }
</style>
