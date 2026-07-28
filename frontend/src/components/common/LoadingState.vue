<script setup lang="ts">defineProps<{ label?: string; rows?: number }>()</script>
<template><section class="loading-state" role="status" :aria-label="label || '正在加载'"><div v-for="index in (rows || 4)" :key="index" class="skeleton"><i></i><span></span><em></em></div></section></template>
<style scoped>
.loading-state { padding: 12px 0; display: grid; gap: 8px; }.skeleton { height: 54px; padding: 0 14px; display: grid; grid-template-columns: 30px 1fr 100px; gap: 12px; align-items: center; border-bottom: 1px solid var(--border-color); }.skeleton i, .skeleton span, .skeleton em { height: 10px; border-radius: 3px; background: linear-gradient(90deg,#edf1f5,#f7f9fb,#edf1f5); background-size: 200% 100%; animation: shine 1.4s linear infinite; }.skeleton i { width: 24px; }.skeleton em { width: 80px; }@keyframes shine { to { background-position: -200% 0; } }@media (prefers-reduced-motion: reduce) { .skeleton i,.skeleton span,.skeleton em { animation: none; } }
</style>
