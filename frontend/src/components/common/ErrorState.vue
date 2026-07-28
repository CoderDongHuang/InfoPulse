<script setup lang="ts">
defineProps<{ title?: string; message: string; diagnosticId?: string; retryLabel?: string }>()
defineEmits<{ retry: [] }>()
</script>
<template><section class="error-state" role="alert"><el-icon><Warning /></el-icon><div><h2>{{ title || '暂时无法加载' }}</h2><p>{{ message }}</p><small v-if="diagnosticId">诊断编号：{{ diagnosticId }}</small></div><button v-if="retryLabel" type="button" @click="$emit('retry')">{{ retryLabel }}</button></section></template>
<style scoped>
.error-state { min-height: 108px; padding: 20px; border: 1px solid #fecaca; border-radius: 6px; display: grid; grid-template-columns: 28px 1fr auto; gap: 14px; align-items: center; background: #fffafa; }.error-state > .el-icon { color: var(--color-danger); font-size: 24px; }.error-state h2 { margin: 0; font-size: 15px; }.error-state p { margin: 4px 0 0; color: var(--text-secondary); font-size: 12px; }.error-state small { display: block; margin-top: 6px; color: var(--text-secondary); font-family: "Cascadia Code", monospace; }.error-state button { min-height: 34px; padding: 0 12px; border: 1px solid #f3a7a7; border-radius: 5px; color: #b91c1c; background: white; cursor: pointer; }
@media (max-width: 560px) { .error-state { grid-template-columns: 28px 1fr; }.error-state button { grid-column: 2; justify-self: start; } }
</style>
