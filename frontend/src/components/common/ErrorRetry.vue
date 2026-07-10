<script setup lang="ts">
defineProps<{
  message?: string
}>()

const emit = defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="error-retry">
    <div class="error-icon">⚠️</div>
    <h3 class="error-title">出错了</h3>
    <p class="error-message">{{ message || '请求失败，请稍后重试' }}</p>
    <el-button type="primary" @click="emit('retry')">
      🔄 重试
    </el-button>
  </div>
</template>

<style scoped>
.error-retry {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.error-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.error-title {
  font-size: 16px;
  color: var(--color-danger);
  margin-bottom: 8px;
}

.error-message {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 20px;
}
</style>
