<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { avatarPreviewStyle, avatarWheelZoom, drawAvatarCrop, encodeAvatarCrop, panAvatarCrop, validateAvatarDimensions, validateAvatarSource, zoomAvatarCrop, type AvatarCropPosition } from '@/utils/avatarCrop'
import { validateAvatarFile } from '@/utils/profile'

const props = defineProps<{ file: File; busy: boolean; uploadError?: string }>()
const emit = defineEmits<{ cancel: []; confirm: [file: File] }>()
const dialog = ref<HTMLDialogElement | null>(null), stage = ref<HTMLDivElement | null>(null)
const ready = ref(false), encoding = ref(false), error = ref('')
const zoom = ref(1), horizontal = ref(.5), vertical = ref(.5)
const dimensions = ref({ width: 0, height: 0 })
const objectUrl = ref('')
let source: HTMLImageElement | null = null, disposed = false, cancelled = false
let drag: { id: number; x: number; y: number; position: AvatarCropPosition; width: number } | null = null
const position = (): AvatarCropPosition => ({ zoom: zoom.value, horizontal: horizontal.value, vertical: vertical.value })
const previewStyle = computed(() => ready.value ? avatarPreviewStyle(dimensions.value.width, dimensions.value.height, position()) : {})
function applyPosition(value: AvatarCropPosition) { zoom.value = value.zoom; horizontal.value = value.horizontal; vertical.value = value.vertical }
function scale(nextZoom: number, anchorX = .5, anchorY = .5) {
  if (!ready.value || props.busy || encoding.value || drag) return
  applyPosition(zoomAvatarCrop(dimensions.value.width, dimensions.value.height, position(), nextZoom, anchorX, anchorY))
}
function wheel(event: WheelEvent) {
  if (!stage.value) return
  const bounds = stage.value.getBoundingClientRect()
  scale(avatarWheelZoom(zoom.value, event.deltaY, event.deltaMode, bounds.width), (event.clientX - bounds.left) / bounds.width, (event.clientY - bounds.top) / bounds.height)
}
function keydown(event: KeyboardEvent) {
  if (!ready.value || props.busy || encoding.value || drag || event.ctrlKey || event.metaKey || event.altKey) return
  const moves: Record<string, [number, number]> = { ArrowLeft: [-12, 0], ArrowRight: [12, 0], ArrowUp: [0, -12], ArrowDown: [0, 12] }
  if (event.key === '+' || event.key === '=') { event.preventDefault(); scale(zoom.value * 1.2) }
  else if (event.key === '-') { event.preventDefault(); scale(zoom.value / 1.2) }
  else if (moves[event.key] && stage.value) {
    event.preventDefault()
    const [dx, dy] = moves[event.key]
    applyPosition(panAvatarCrop(dimensions.value.width, dimensions.value.height, position(), dx, dy, stage.value.getBoundingClientRect().width))
  }
}

async function confirm() {
  if (!ready.value || !source || props.busy || encoding.value || cancelled || disposed) return
  encoding.value = true; error.value = ''
  try {
    const output = document.createElement('canvas')
    drawAvatarCrop(output, source, zoom.value, horizontal.value, vertical.value)
    const file = await encodeAvatarCrop(output)
    validateAvatarFile(file)
    if (!disposed && !cancelled) emit('confirm', file)
  } catch (cause) {
    if (!disposed && !cancelled) error.value = cause instanceof Error ? cause.message : '裁剪失败。'
  } finally { if (!disposed) encoding.value = false }
}
function cancel(event?: Event) { event?.preventDefault(); if (!props.busy) { cancelled = true; emit('cancel') } }
function dragStart(event: PointerEvent) {
  if (!ready.value || props.busy || encoding.value || !stage.value || event.button !== 0) return
  event.preventDefault()
  stage.value.focus()
  drag = { id: event.pointerId, x: event.clientX, y: event.clientY, position: position(), width: stage.value.getBoundingClientRect().width }
  stage.value.setPointerCapture(event.pointerId)
}
function dragMove(event: PointerEvent) {
  if (!drag || drag.id !== event.pointerId || props.busy) return
  const { width, height } = dimensions.value
  applyPosition(panAvatarCrop(width, height, drag.position, event.clientX - drag.x, event.clientY - drag.y, drag.width))
}
function dragEnd(event: PointerEvent) { if (drag?.id === event.pointerId) drag = null }
onMounted(async () => {
  dialog.value?.showModal()
  try {
    validateAvatarSource(props.file)
    objectUrl.value = URL.createObjectURL(props.file)
    const image = new Image()
    source = image
    await new Promise<void>((resolve, reject) => { image.onload = () => resolve(); image.onerror = () => reject(new Error('无法读取图片，请选择有效的 PNG、JPEG 或 WebP。')); image.src = objectUrl.value })
    if (disposed) return
    validateAvatarDimensions(image.naturalWidth, image.naturalHeight)
    dimensions.value = { width: image.naturalWidth, height: image.naturalHeight }
    ready.value = true
    await nextTick()
    if (!disposed) stage.value?.focus({ preventScroll: true })
  } catch (cause) { if (!disposed) error.value = cause instanceof Error ? cause.message : '图片读取失败。' }
})
onBeforeUnmount(() => {
  disposed = true
  dialog.value?.close()
  if (source) { source.onload = null; source.onerror = null; source.src = '' }
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value)
})
</script>
<template>
  <dialog ref="dialog" class="avatar-cropper" aria-labelledby="crop-title" aria-describedby="crop-help" @cancel="cancel">
    <header><div><p class="crop-eyebrow">AVATAR / 头像</p><h2 id="crop-title">裁剪头像</h2></div><button type="button" class="close" aria-label="取消裁剪" :disabled="busy" @click="cancel()">×</button></header>
    <p id="crop-help">拖动调整位置，滚轮或 + / − 键缩放。圆圈内就是头像。</p>
    <p v-if="!ready && !error" role="status">正在读取本地图片…</p>
    <div v-show="ready" class="crop-workspace">
      <div ref="stage" class="crop-stage" tabindex="0" role="img" aria-label="头像裁剪预览" aria-describedby="crop-keys" @wheel.prevent="wheel" @keydown="keydown" @pointerdown="dragStart" @pointermove="dragMove" @pointerup="dragEnd" @pointercancel="dragEnd" @lostpointercapture="dragEnd"><img v-if="objectUrl" :src="objectUrl" :style="previewStyle" alt="" draggable="false" /><div class="circle-guide" /></div>
      <span id="crop-keys" class="sr-only">也可用加减键缩放，方向键移动图片。</span>
    </div>
    <p v-if="error || uploadError" class="crop-error" role="alert">{{ error || uploadError }}</p>
    <footer><button type="button" class="secondary" :disabled="busy" @click="cancel()">取消</button><button type="button" class="primary" :disabled="busy || encoding || !ready" @click="confirm">{{ busy ? '正在保存…' : encoding ? '正在生成…' : '确认并保存' }}</button></footer>
  </dialog>
</template>
<style scoped>
.avatar-cropper{box-sizing:border-box;width:min(440px,calc(100vw - 32px));max-height:calc(100dvh - 32px);overflow:auto;border:1px solid #dce3ef;border-radius:18px;padding:24px;color:#17243b;background:#fff;box-shadow:0 24px 80px #152b4d33}
.avatar-cropper::backdrop{background:#15243b88}
header{display:flex;align-items:center;justify-content:space-between}h2{font-size:20px;margin:3px 0}.crop-eyebrow{color:#4263bf;font-size:11px;margin:0;letter-spacing:1px}
#crop-help{color:#64748b;font-size:13px;line-height:1.7;margin:14px 0 18px}
.crop-stage{position:relative;aspect-ratio:1;max-width:320px;width:100%;margin:auto;background:repeating-conic-gradient(#edf0f5 0% 25%,#fff 0% 50%) 50%/16px 16px;border-radius:10px;overflow:hidden}
.crop-stage{cursor:grab;touch-action:none;user-select:none}.crop-stage:active{cursor:grabbing}.crop-stage:focus-visible{outline:3px solid #2563eb;outline-offset:2px}.crop-stage img{position:absolute;max-width:none;pointer-events:none;user-select:none}
.circle-guide{position:absolute;inset:0;border:1px dashed #fff;border-radius:50%;box-shadow:0 0 0 100px #12233f55;pointer-events:none}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap;border:0}
button{min-height:38px;border-radius:7px;padding:0 15px;font-size:13px;cursor:pointer}.secondary{background:#fff;border:1px solid #cbd5e1;color:#475569}.primary{background:#2563eb;border:1px solid #2563eb;color:#fff}.close{font-size:26px;border:0;background:transparent;color:#64748b;padding:0 8px}button:disabled{opacity:.5;cursor:not-allowed}
.crop-error{color:#b91c1c;font-size:13px}footer{display:flex;justify-content:flex-end;gap:10px;margin-top:20px;padding-top:18px;border-top:1px solid #e6ebf2}
@media(max-width:520px){.avatar-cropper{padding:20px}}
</style>
