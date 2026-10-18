<script setup lang="ts">
import { onMounted, ref } from 'vue'

const acceptance = ref(false)
const publicUrl = ['127.0.0.1', 'localhost'].includes(window.location.hostname) && window.location.port === '15173'
  ? `http://${window.location.hostname}:15174/` : ''
onMounted(async () => {
  try {
    const response = await fetch('/api/v1/health', { cache: 'no-store' })
    if (response.ok) acceptance.value = (await response.json()).acceptance_mode === true
  } catch { /* A failed health probe must not block login or page-level retry. */ }
})
</script>

<template>
  <aside v-if="acceptance" class="environment-notice" role="note" aria-label="隔离验收环境">
    <strong>隔离验收环境</strong>
    <span>此实例用于功能测试，关闭了自动采集，账号和数据与日常使用环境独立。</span>
    <a v-if="publicUrl" :href="publicUrl">打开真实数据工作台 →</a>
    <span v-else>日常使用请按照 README 的「本地真实公开数据」入口启动。</span>
  </aside>
</template>

<style scoped>
.environment-notice { margin: 16px auto; width: calc(100% - 32px); max-width: 1200px; box-sizing: border-box; padding: 12px 16px; display: flex; align-items: center; flex-wrap: wrap; gap: 6px 12px; border: 1px solid #e8cf94; border-radius: 8px; background: #fffbef; color: #72551d; font-size: 12px; line-height: 1.8; }
.environment-notice a { color: #1d4ed8; font-weight: 600; }
</style>
