<script setup lang="ts">
defineProps<{ title: string; description?: string; actionLabel?: string; icon?: string }>()
defineEmits<{ action: [] }>()
</script>
<template><section class="state"><span class="state-icon"><el-icon><component :is="icon || 'Files'" /></el-icon></span><h2>{{ title }}</h2><p v-if="description">{{ description }}</p><button v-if="actionLabel" type="button" @click="$emit('action')">{{ actionLabel }}</button></section></template>
<style scoped>
.state { min-height: 320px; padding: 32px; display: grid; justify-items: center; align-content: center; text-align: center; }.state-icon { width: 56px; height: 56px; border-radius: 50%; display: grid; place-items: center; color: var(--color-primary); background: #eaf1ff; font-size: 23px; }.state h2 { margin: 16px 0 4px; font-size: 18px; }.state p { max-width: 440px; margin: 0; color: var(--text-secondary); font-size: 13px; }.state button { min-height: 36px; margin-top: 16px; padding: 0 14px; border: 0; border-radius: 5px; color: white; background: var(--color-primary); cursor: pointer; }
</style>
