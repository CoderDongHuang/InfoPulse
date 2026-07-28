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
const setOnline = () => (isOnline.value = true)
const setOffline = () => (isOnline.value = false)

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  window.addEventListener('online', setOnline)
  window.addEventListener('offline', setOffline)
})

onUnmounted(() => {
  clearInterval(timer)
  window.removeEventListener('online', setOnline)
  window.removeEventListener('offline', setOffline)
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
      <span class="status-dot" :class="{ offline: !isOnline }" aria-hidden="true"></span>
      <span class="breadcrumb">{{ (route.meta.title as string) || '首页' }}</span>
    </div>
    <div class="footer-right">
      <span class="footer-item">{{ currentTime }}</span>
      <span class="footer-separator">|</span>
      <span class="footer-item" :class="{ online: isOnline, offline: !isOnline }">
        {{ isOnline ? '在线' : '离线' }}
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
  height: 44px;
  border-top: 1px solid #263b35;
  background: #14231f;
  font-size: 12px;
  color: #82978f;
}

.footer-left,
.footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.footer-separator {
  color: #395049;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success);
  box-shadow: 0 0 0 4px rgba(85, 197, 183, 0.1);
}

.status-dot.offline {
  background: var(--color-danger);
  box-shadow: 0 0 0 4px rgba(239, 116, 108, 0.1);
}

.online { color: var(--color-success); }
.offline { color: var(--color-danger); }

@media (max-width: 768px) {
  .app-footer {
    height: 46px;
    padding: 0 14px;
  }

  .app-footer::after {
    content: 'INFOPULSE / PUBLIC SIGNAL DESK';
    color: #60756e;
    font: 700 8px/1 "Cascadia Code", monospace;
  }

  .footer-right {
    display: none;
  }
}
</style>
