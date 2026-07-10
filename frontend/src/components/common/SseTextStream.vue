<script setup lang="ts">
/**
 * InfoPulse — SSE Text Stream (Typewriter Effect)
 * =================================================
 * Receives progressively appended text and renders it with
 * a simulated typewriter cursor effect.
 */
import { watch, ref, nextTick } from 'vue'

const props = defineProps<{
  text: string
}>()

const containerRef = ref<HTMLElement>()

// Auto-scroll to bottom when new text arrives
watch(() => props.text, async () => {
  await nextTick()
  if (containerRef.value) {
    containerRef.value.scrollTop = containerRef.value.scrollHeight
  }
})
</script>

<template>
  <div ref="containerRef" class="sse-text-stream">
    <div class="stream-content" v-html="text || '<span class=\'cursor-blink\'>▊</span>'"></div>
  </div>
</template>

<style scoped>
.sse-text-stream {
  max-height: 400px;
  overflow-y: auto;
  padding: 16px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
}

.stream-content {
  min-height: 24px;
}

.cursor-blink {
  animation: blink 1s step-end infinite;
  color: var(--color-primary);
}

@keyframes blink {
  50% { opacity: 0; }
}
</style>
