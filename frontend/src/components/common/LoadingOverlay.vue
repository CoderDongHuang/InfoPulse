<script setup lang="ts">
defineProps<{
  visible: boolean
  text?: string
}>()
</script>

<template>
  <transition name="fade">
    <div v-if="visible" class="loading-overlay">
      <div class="loading-box glass-card">
        <el-icon class="loading-icon" :size="40"><Loading /></el-icon>
        <p class="loading-text">{{ text || '加载中...' }}</p>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.loading-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px 60px;
}

.loading-icon {
  animation: spin 1s linear infinite;
  color: var(--color-primary);
}

.loading-text {
  font-size: 15px;
  color: var(--text-regular);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
