<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { automationApi } from '@/api/automation'
import { useUserStore } from '@/stores/user'

const route = useRoute(), router = useRouter()
const query = ref(''), unread = ref(0)
let unreadTimer: ReturnType<typeof setInterval> | undefined
let disposed = false
async function loadUnread() {
  if (!useUserStore().isLoggedIn) return
  try { const result = await automationApi.unreadCount(); if (!disposed) unread.value = result.count }
  catch { if (!disposed) unread.value = 0 }
}
onMounted(() => { void loadUnread(); unreadTimer = setInterval(loadUnread, 30000) })
onBeforeUnmount(() => { disposed = true; clearInterval(unreadTimer) })
function search() {
  const value = query.value.trim()
  if (value) void router.push({ path: '/search', query: { q: value } })
}
</script>
<template>
  <div class="toolbar">
    <div class="toolbar-inner">
      <div class="context"><span>工作空间</span><i>/</i><strong>{{ route.meta.title || 'InfoPulse' }}</strong></div>
      <form class="global-search" role="search" @submit.prevent="search">
        <el-icon><Search /></el-icon><input v-model="query" aria-label="全局搜索" placeholder="搜索事件、企业或关键词" />
        <button type="submit" aria-label="执行全局搜索"><el-icon><Right /></el-icon></button>
      </form>
      <div class="tools">
        <button class="notification-button" type="button" title="通知中心" aria-label="通知中心" @click="router.push('/notifications')"><el-icon><Bell /></el-icon><span v-if="unread">{{ unread > 99 ? '99+' : unread }}</span></button>
        <button class="ai-button" type="button" @click="router.push('/agent')"><el-icon><MagicStick /></el-icon><span>询问 AI</span></button>
      </div>
    </div>
  </div>
</template>
<style scoped>
.toolbar { position: fixed; left: 0; right: 0; top: 68px; z-index: 90; height: 56px; border-bottom: 1px solid var(--border-color); background: #fff; }
.toolbar-inner { max-width: 1600px; height: 100%; margin: auto; padding: 0 32px; display: flex; align-items: center; gap: 24px; }.context { display: flex; align-items: center; gap: 12px; font-size: 12px; min-width: 0; }.context span, .context i { color: var(--text-secondary); font-style: normal; }.context strong { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.global-search { margin-left: auto; width: min(380px, 40vw); height: 34px; padding: 0 6px 0 11px; display: grid; grid-template-columns: 16px minmax(0, 1fr) 24px; gap: 8px; align-items: center; border: 1px solid #e2e8f0; border-radius: 7px; color: #64748b; background: #f8fafc; }.global-search:focus-within { border-color: #2563eb; }.global-search input { min-width: 0; border: 0; background: transparent; outline: none; color: var(--text-primary); font-size: 12px; }.global-search button { border: 0; background: transparent; color: #64748b; cursor: pointer; display: grid; place-items: center; padding: 0; height: 26px; }
.tools { display: flex; gap: 10px; }.tools button { height: 34px; padding: 0 11px; display: flex; align-items: center; gap: 7px; border-radius: 7px; cursor: pointer; font-size: 12px; }.notification-button { position: relative; border: 1px solid #e2e8f0; color: #475569; background: #fff; }.notification-button > span { position: absolute; right: -5px; top: -5px; padding: 1px 4px; border-radius: 8px; color: #fff; background: #b91c1c; font-size: 9px; }.ai-button { border: 1px solid #dbe5fa; color: #2453ae; background: #f0f5ff; }
@media (max-width: 720px) { .toolbar { height: 52px; }.toolbar-inner { padding: 0 16px; gap: 12px; }.context { display: none; }.global-search { flex: 1; margin-left: 0; width: auto; }.tools { gap: 7px; }.ai-button span { display: none; } }
</style>
