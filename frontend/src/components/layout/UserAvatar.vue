<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { safeAvatarUrl } from '@/utils/profile'
const props = defineProps<{ username?: string; url?: string }>()
const failed = ref(false)
const url = computed(() => safeAvatarUrl(props.url || ''))
watch(url, () => { failed.value = false })
</script>
<template>
  <span class="user-avatar" aria-hidden="true">
    <img v-if="url && !failed" :src="url" alt="" referrerpolicy="no-referrer" @error="failed = true" />
    <span v-else>{{ Array.from(username || 'U')[0]?.toUpperCase() }}</span>
  </span>
</template>
<style scoped>
.user-avatar { width: 36px; height: 36px; flex: 0 0 auto; border-radius: 50%; display: inline-grid; place-items: center; overflow: hidden; background: #e8efff; color: #2453ae; font-weight: 700; }
.user-avatar img { width: 100%; height: 100%; object-fit: cover; }
</style>
