import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { File, Blob } from 'node:buffer'
import vm from 'node:vm'
import ts from 'typescript'
import { computed, nextTick, ref } from 'vue'

function load(path) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const context = { exports: {}, File, Blob, URL, Error }
  vm.runInNewContext(code, context)
  return context.exports
}
const crop = load('../src/utils/avatarCrop.ts')
const profile = load('../src/utils/profile.ts')

test('crop dialog uses direct manipulation without numeric controls or a toolbar', () => {
  const source = readFileSync(new URL('../src/components/common/AvatarCropper.vue', import.meta.url), 'utf8')
  const template = source.split('<template>')[1].split('</template>')[0]
  assert.doesNotMatch(template, /<(?:input|select|output)\b|crop-tools|crop-size|当前缩放|重置/)
  assert.equal((template.match(/<button\b/g) || []).length, 3) // Close, cancel and confirm only.
  for (const binding of ['@wheel.prevent="wheel"', '@keydown="keydown"', '@pointerdown="dragStart"', '@pointermove="dragMove"']) {
    assert.ok(template.includes(binding))
  }
  assert.ok(source.includes('stage.value?.focus({ preventScroll: true })'))
  assert.ok(source.includes('validateAvatarFile(file)'))
  assert.match(template, /确认并保存/)
})

test('original byte size is never used as an upload limit', () => {
  for (const type of ['image/png', 'image/jpeg', 'image/webp']) {
    for (const size of [3, 21, 100, 1024]) assert.doesNotThrow(() => crop.validateAvatarSource({ type, size: size * 1024 * 1024 }))
  }
  assert.throws(() => profile.validateAvatarFile({ type: 'image/png', size: 3 * 1024 * 1024 }))
  assert.throws(() => crop.validateAvatarSource({ type: 'image/svg+xml', size: 100 }))
  assert.throws(() => crop.validateAvatarSource({ type: 'image/png', size: 0 }))
})

test('crop stays inside portrait, landscape and square originals at every edge', () => {
  for (const [width, height] of [[1200, 800], [800, 1200], [800, 800]]) {
    for (const zoom of [1, 2, 4]) {
      for (const horizontal of [0, .5, 1]) for (const vertical of [0, .5, 1]) {
        const rect = crop.avatarCropRect(width, height, zoom, horizontal, vertical)
        assert.equal(rect.size, Math.min(width, height) / zoom)
        assert.ok(rect.x >= 0 && rect.y >= 0)
        assert.ok(rect.x + rect.size <= width && rect.y + rect.size <= height)
      }
    }
  }
  assert.equal(JSON.stringify(crop.avatarCropRect(1200, 800, 1, .5, .5)), JSON.stringify({ x: 200, y: 0, size: 800 }))
  assert.equal(JSON.stringify(crop.avatarCropRect(1200, 800, 4, 1, 1)), JSON.stringify({ x: 1000, y: 600, size: 200 }))
})

test('invalid dimensions fail and untrusted crop settings are clamped', () => {
  for (const dimensions of [[0, 20], [-1, 20], [Infinity, 20], [NaN, 20]]) {
    assert.throws(() => crop.avatarCropRect(...dimensions, 1, .5, .5))
  }
  assert.doesNotThrow(() => crop.validateAvatarDimensions(10000, 10000))
  assert.equal(JSON.stringify(crop.avatarCropRect(1200, 800, -10, -2, 30)), JSON.stringify({ x: 0, y: 0, size: 800 }))
  assert.equal(crop.avatarCropRect(1200, 800, 20, NaN, Infinity).size, 200)
})

test('canvas exports exactly the chosen source square, without stale pixels', () => {
  const calls = []
  const context = { clearRect: (...args) => calls.push(['clear', ...args]), drawImage: (...args) => calls.push(['draw', ...args]) }
  const canvas = { width: 300, height: 150, getContext: () => context }
  const image = { naturalWidth: 1200, naturalHeight: 800 }
  crop.drawAvatarCrop(canvas, image, 2, 1, .5)
  assert.deepEqual(calls, [['clear', 0, 0, 512, 512], ['draw', image, 800, 200, 400, 400, 0, 0, 512, 512]])
  assert.equal(canvas.width, 512)
  assert.equal(canvas.height, 512)
  assert.equal(context.imageSmoothingQuality, 'high')
  assert.throws(() => crop.drawAvatarCrop({ getContext: () => null }, image, 1, .5, .5), /无法裁剪/)
})

test('only the encoded crop is validated for upload size; encoding failure is recoverable', async () => {
  const encoded = new Blob(['cropped-image'], { type: 'image/webp' })
  const file = await crop.encodeAvatarCrop({ toBlob: (callback, type, quality) => { assert.equal(type, 'image/webp'); assert.equal(quality, .9); callback(encoded) } })
  assert.equal(file.name, 'avatar.webp')
  assert.equal(file.size, encoded.size)
  assert.equal(file.type, 'image/webp')
  assert.doesNotThrow(() => profile.validateAvatarFile(file))
  const tooLarge = await crop.encodeAvatarCrop({ toBlob: callback => callback(new Blob([new Uint8Array(2097153)], { type: 'image/webp' })) })
  assert.throws(() => profile.validateAvatarFile(tooLarge), /2 MB/)
  await assert.rejects(crop.encodeAvatarCrop({ toBlob: callback => callback(null) }), /生成失败/)
  await assert.rejects(crop.encodeAvatarCrop({ toBlob: callback => callback(new Blob(['fallback'], { type: 'image/png' })) }), /不支持生成 WebP/)
  assert.doesNotThrow(() => profile.validateAvatarFile({ type: 'image/webp', size: 2097152 }))
})

test('fixed preview frame shows the same crop as the exported image at every edge', () => {
  for (const [width, height] of [[1200, 800], [800, 1200], [800, 800]]) {
    for (const zoom of [1, 2, 4]) for (const horizontal of [0, .5, 1]) for (const vertical of [0, .5, 1]) {
      const p = { zoom, horizontal, vertical }
      const rect = crop.avatarCropRect(width, height, zoom, horizontal, vertical)
      const style = crop.avatarPreviewStyle(width, height, p)
      assert.equal(parseFloat(style.width), width / rect.size * 100)
      assert.equal(parseFloat(style.height), height / rect.size * 100)
      assert.equal(parseFloat(style.left) || 0, -rect.x / rect.size * 100 || 0)
      assert.equal(parseFloat(style.top) || 0, -rect.y / rect.size * 100 || 0)
      assert.ok(parseFloat(style.left) <= 0 && parseFloat(style.top) <= 0)
      assert.ok(parseFloat(style.left) + parseFloat(style.width) >= 100 - 1e-8)
      assert.ok(parseFloat(style.top) + parseFloat(style.height) >= 100 - 1e-8)
    }
  }
})

async function cropComponent({ encode = async () => new File(['webp'], 'avatar.webp', { type: 'image/webp' }) } = {}) {
  const source = readFileSync(new URL('../src/components/common/AvatarCropper.vue', import.meta.url), 'utf8').split('<script setup lang="ts">')[1].split('</script>')[0]
  const callbacks = {}, events = [], calls = { draw: 0, encode: 0, revoked: 0 }
  const props = { file: new File(['source'], 'large.png', { type: 'image/png' }), busy: false }
  const context = {
    exports: {}, Error, defineProps: () => props, defineEmits: () => (...args) => events.push(args),
    Image: class {
      naturalWidth = 1200; naturalHeight = 800
      set src(value) { if (value) Promise.resolve().then(() => this.onload?.()) }
    },
    URL: { createObjectURL: () => 'blob:local-only', revokeObjectURL: () => calls.revoked++ },
    document: { createElement: type => { assert.equal(type, 'canvas'); return {} } },
    require: path => {
      if (path === 'vue') return { computed, nextTick, ref, onMounted: fn => { callbacks.mount = fn }, onBeforeUnmount: fn => { callbacks.unmount = fn } }
      if (path === '@/utils/profile') return profile
      if (path === '@/utils/avatarCrop') return { ...crop, drawAvatarCrop: () => calls.draw++, encodeAvatarCrop: canvas => { calls.encode++; return encode(canvas) } }
      throw new Error(`Unexpected import ${path}`)
    },
  }
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  vm.runInNewContext(code + '\nexports.ui = { confirm, cancel, stage, error, encoding, wheel, keydown };', context)
  const ui = context.exports.ui
  ui.stage.value = { focus() {}, getBoundingClientRect: () => ({ left: 0, top: 0, width: 320, height: 320 }) }
  await callbacks.mount()
  return { ui, calls, events, callbacks, props }
}

test('selecting, zooming and cancelling never encode or upload the original', async () => {
  const { ui, calls, events, callbacks } = await cropComponent()
  ui.wheel({ deltaY: -100, deltaMode: 0, clientX: 100, clientY: 100 })
  ui.keydown({ key: '+', preventDefault() {} })
  assert.equal(calls.draw, 0)
  assert.equal(calls.encode, 0)
  assert.equal(events.length, 0)
  ui.cancel()
  await ui.confirm()
  assert.deepEqual(events.map(event => event[0]), ['cancel'])
  callbacks.unmount()
  assert.equal(calls.revoked, 1)
})

test('confirmation encodes once, checks the result then emits only the cropped WebP', async () => {
  const { ui, calls, events, callbacks } = await cropComponent()
  await ui.confirm()
  assert.equal(calls.draw, 1)
  assert.equal(calls.encode, 1)
  assert.equal(events.length, 1)
  assert.equal(events[0][0], 'confirm')
  assert.equal(events[0][1].type, 'image/webp')
  assert.equal(events[0][1].name, 'avatar.webp')
  callbacks.unmount()
})

test('oversize or failed crop never uploads and can be retried', async () => {
  let attempt = 0
  const { ui, events, callbacks } = await cropComponent({ encode: async () => {
    if (++attempt === 1) return new File([new Uint8Array(2097153)], 'avatar.webp', { type: 'image/webp' })
    if (attempt === 2) throw new Error('encode failed')
    return new File(['ok'], 'avatar.webp', { type: 'image/webp' })
  } })
  await ui.confirm()
  assert.match(ui.error.value, /2 MB/)
  assert.equal(events.length, 0)
  await ui.confirm()
  assert.equal(ui.error.value, 'encode failed')
  assert.equal(events.length, 0)
  await ui.confirm()
  assert.equal(events.length, 1)
  callbacks.unmount()
})

test('double confirmation and cancellation during encoding cannot publish a late upload', async () => {
  let resolve
  const pending = new Promise(done => { resolve = done })
  const { ui, calls, events, callbacks } = await cropComponent({ encode: () => pending })
  const first = ui.confirm()
  await ui.confirm()
  assert.equal(calls.encode, 1)
  ui.cancel()
  callbacks.unmount()
  resolve(new File(['late'], 'avatar.webp', { type: 'image/webp' }))
  await first
  assert.deepEqual(events.map(event => event[0]), ['cancel'])
})

test('wheel zoom supports pixels, lines and pages and clamps both limits', () => {
  assert.ok(crop.avatarWheelZoom(2, -100) > 2)
  assert.ok(crop.avatarWheelZoom(2, 100) < 2)
  assert.equal(crop.avatarWheelZoom(2, -1, 1), crop.avatarWheelZoom(2, -16))
  assert.equal(crop.avatarWheelZoom(2, 1, 2, 120), crop.avatarWheelZoom(2, 120))
  assert.equal(crop.avatarWheelZoom(4, -10000), 4)
  assert.equal(crop.avatarWheelZoom(1, 10000), 1)
  assert.equal(crop.avatarWheelZoom(2, 0), 2)
  assert.equal(crop.avatarWheelZoom(2, NaN), 2)
})

test('cursor-centered zoom keeps the selected image point stationary and stays inside the image', () => {
  const position = { zoom: 1.5, horizontal: .5, vertical: .5 }
  const before = crop.avatarCropRect(1200, 800, position.zoom, position.horizontal, position.vertical)
  const next = crop.zoomAvatarCrop(1200, 800, position, 3, .25, .75)
  const after = crop.avatarCropRect(1200, 800, next.zoom, next.horizontal, next.vertical)
  assert.ok(Math.abs(before.x + before.size * .25 - after.x - after.size * .25) < 1e-8)
  assert.ok(Math.abs(before.y + before.size * .75 - after.y - after.size * .75) < 1e-8)
  for (const [width, height] of [[1200, 800], [800, 1200], [800, 800]]) {
    for (const zoom of [-5, 1, 2, 4, 20]) for (const anchor of [0, .5, 1]) {
      const moved = crop.zoomAvatarCrop(width, height, { zoom: 3, horizontal: 1, vertical: 0 }, zoom, anchor, anchor)
      const rect = crop.avatarCropRect(width, height, moved.zoom, moved.horizontal, moved.vertical)
      assert.ok(moved.zoom >= 1 && moved.zoom <= 4)
      assert.ok(rect.x >= 0 && rect.y >= 0 && rect.x + rect.size <= width && rect.y + rect.size <= height)
    }
  }
})

test('drag follows the pointer, remains bounded and can pan square images after zooming', () => {
  const position = { zoom: 2, horizontal: .5, vertical: .5 }
  const right = crop.panAvatarCrop(1200, 800, position, 80, -80, 320)
  assert.equal(right.horizontal, .375)
  assert.equal(right.vertical, .75)
  const edge = crop.panAvatarCrop(800, 800, position, 10000, -10000, 320)
  assert.equal(edge.horizontal, 0)
  assert.equal(edge.vertical, 1)
  const full = crop.panAvatarCrop(800, 800, { ...position, zoom: 1 }, 10, 10, 320)
  assert.equal(full.horizontal, .5)
  assert.equal(full.vertical, .5)
  assert.equal(crop.panAvatarCrop(1200, 800, position, 10, 10, 0), position)
})
