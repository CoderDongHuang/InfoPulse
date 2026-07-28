<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const query = ref('')

function search() {
  const value = query.value.trim()
  if (value) void router.push({ path: '/insight', query: { q: value } })
}
</script>

<template>
  <header class="toolbar">
    <div class="context"><span>{{ route.meta.title || 'InfoPulse' }}</span><small>AI Intelligence Platform</small></div>
    <form class="global-search" role="search" @submit.prevent="search">
      <el-icon><Search /></el-icon>
      <input v-model="query" aria-label="全局搜索" placeholder="搜索事件、企业、人物或关键词" />
      <button type="submit" title="执行全局搜索" aria-label="执行全局搜索"><el-icon><Right /></el-icon></button>
    </form>
    <div class="tools">
      <button class="source-state" type="button" title="查看当前数据源状态" @click="router.push('/hot-search')"><i></i><span>兼容数据源</span></button>
      <button class="ai-button" type="button" title="使用现有洞察能力快速分析" @click="router.push('/insight')"><el-icon><MagicStick /></el-icon><span>询问 AI</span></button>
    </div>
  </header>
</template>

<style scoped>
.toolbar { position: fixed; left: 220px; right: 0; top: 0; z-index: 90; height: 56px; padding: 0 20px; display: grid; grid-template-columns: minmax(150px, .5fr) minmax(280px, 620px) minmax(190px, .5fr); gap: 18px; align-items: center; border-bottom: 1px solid var(--border-color); background: rgba(255,255,255,.94); backdrop-filter: blur(14px); }.context { min-width: 0; display: flex; flex-direction: column; line-height: 1.2; }.context span { overflow: hidden; font-size: 13px; font-weight: 650; white-space: nowrap; text-overflow: ellipsis; }.context small { margin-top: 3px; color: var(--text-secondary); font-size: 10px; }.global-search { height: 36px; padding: 0 6px 0 10px; display: grid; grid-template-columns: 18px 1fr auto; gap: 8px; align-items: center; border: 1px solid var(--border-color); border-radius: 6px; background: var(--surface-soft); }.global-search:focus-within { border-color: var(--color-primary); box-shadow: 0 0 0 3px rgba(37,99,235,.1); }.global-search input { min-width: 0; border: 0; outline: 0; color: var(--text-primary); background: transparent; font-size: 12px; }.global-search > button { width: 26px; height: 26px; padding: 0; border: 0; border-radius: 4px; display: grid; place-items: center; color: var(--text-secondary); background: transparent; cursor: pointer; }.global-search > button:hover { color: var(--color-primary); background: #e5edff; }.tools { display: flex; justify-content: flex-end; gap: 8px; }.tools button { height: 34px; padding: 0 11px; border-radius: 5px; display: flex; align-items: center; gap: 7px; cursor: pointer; font-size: 11px; }.source-state { border: 1px solid var(--border-color); color: var(--text-regular); background: white; }.source-state i { width: 7px; height: 7px; border-radius: 50%; background: var(--color-warning); }.ai-button { border: 1px solid #1d4ed8; color: white; background: var(--color-primary); }
@media (max-width: 980px) { .toolbar { left: 72px; grid-template-columns: 1fr minmax(260px, 480px) auto; }.context small, .source-state span { display: none; } }
@media (max-width: 720px) { .toolbar { position: fixed; left: 0; top: 64px; height: 52px; padding: 0 12px; grid-template-columns: 1fr auto; }.context, .source-state { display: none !important; }.global-search { height: 36px; }.ai-button span { display: none; } }
</style>
