<script setup lang="ts">
/**
 * InfoPulse — App Footer / Status Bar
 * =====================================
 * Breadcrumb navigation + system time + network status + copyright.
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const currentTime = ref('')
const isOnline = ref(navigator.onLine)
let timer: ReturnType<typeof setInterval>

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  window.addEventListener('online', () => (isOnline.value = true))
  window.addEventListener('offline', () => (isOnline.value = false))
})

onUnmounted(() => {
  clearInterval(timer)
})

function updateTime() {
  currentTime.value = new Date().toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
</script>

<template>
  <footer class="app-footer">
    <div class="footer-left">
      <span class="breadcrumb">{{ (route.meta.title as string) || '首页' }}</span>
    </div>
    <div class="footer-right">
      <span class="footer-item">{{ currentTime }}</span>
      <span class="footer-separator">|</span>
      <span class="footer-item" :class="{ online: isOnline, offline: !isOnline }">
        {{ isOnline ? '🌐 在线' : '⚠️ 离线' }}
      </span>
      <span class="footer-separator">|</span>
      <span class="footer-item">&copy; 2026 InfoPulse</span>
    </div>
  </footer>
</template>

<style scoped>
.app-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 40px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-card);
  font-size: 12px;
  color: var(--text-secondary);
}

.footer-left,
.footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.footer-separator {
  color: var(--border-color);
}

.online { color: var(--color-success); }
.offline { color: var(--color-danger); }

@media (max-width: 768px) {
  .footer-right {
    display: none;
  }
}
</style>
