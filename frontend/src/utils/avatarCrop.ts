/** Crop coordinates are expressed in original, orientation-corrected image pixels. */
export const AVATAR_OUTPUT_SIZE = 512

export function validateAvatarSource(file: Pick<File, 'type' | 'size'>): void {
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) throw new Error('请选择 PNG、JPEG 或 WebP 图片。')
  if (!file.size) throw new Error('请选择非空图片。')
}

export function validateAvatarDimensions(width: number, height: number): void {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    throw new Error('无法读取图片尺寸，请重新选择有效图片。')
  }
}

export function avatarCropRect(width: number, height: number, zoom: number, horizontal: number, vertical: number) {
  validateAvatarDimensions(width, height)
  const bounded = (value: number, min: number, max: number) => Math.min(max, Math.max(min, Number.isFinite(value) ? value : min))
  const size = Math.min(width, height) / bounded(zoom, 1, 4)
  return { x: (width - size) * bounded(horizontal, 0, 1), y: (height - size) * bounded(vertical, 0, 1), size }
}

export type AvatarCropPosition = { zoom: number; horizontal: number; vertical: number }

/** Scale and move the original image inside a fixed, overflow-hidden crop frame. */
export function avatarPreviewStyle(width: number, height: number, position: AvatarCropPosition) {
  const { x, y, size } = avatarCropRect(width, height, position.zoom, position.horizontal, position.vertical)
  return { width: `${width / size * 100}%`, height: `${height / size * 100}%`, left: `${-x / size * 100}%`, top: `${-y / size * 100}%` }
}

/** Keep the image point under the cursor stationary when zooming, unless an edge is reached. */
export function zoomAvatarCrop(width: number, height: number, position: AvatarCropPosition, nextZoom: number, anchorX = .5, anchorY = .5): AvatarCropPosition {
  const clamp = (value: number) => Math.max(0, Math.min(1, Number.isFinite(value) ? value : .5))
  const before = avatarCropRect(width, height, position.zoom, position.horizontal, position.vertical)
  const zoom = Math.max(1, Math.min(4, Number.isFinite(nextZoom) ? nextZoom : position.zoom))
  const after = avatarCropRect(width, height, zoom, .5, .5)
  return {
    zoom,
    horizontal: width > after.size ? clamp((before.x + (before.size - after.size) * clamp(anchorX)) / (width - after.size)) : .5,
    vertical: height > after.size ? clamp((before.y + (before.size - after.size) * clamp(anchorY)) / (height - after.size)) : .5,
  }
}

export function panAvatarCrop(width: number, height: number, position: AvatarCropPosition, dx: number, dy: number, previewWidth: number): AvatarCropPosition {
  const { size } = avatarCropRect(width, height, position.zoom, position.horizontal, position.vertical)
  if (!Number.isFinite(previewWidth) || previewWidth <= 0) return position
  const clamp = (value: number) => Math.max(0, Math.min(1, value))
  return {
    zoom: position.zoom,
    horizontal: width > size ? clamp(position.horizontal - dx * size / previewWidth / (width - size)) : .5,
    vertical: height > size ? clamp(position.vertical - dy * size / previewWidth / (height - size)) : .5,
  }
}

/** deltaMode: pixels (0), lines (1), pages (2), as defined by WheelEvent. */
export function avatarWheelZoom(zoom: number, delta: number, deltaMode = 0, previewWidth = 320): number {
  if (!Number.isFinite(delta) || delta === 0) return zoom
  const pixels = delta * (deltaMode === 1 ? 16 : deltaMode === 2 ? previewWidth : 1)
  return Math.max(1, Math.min(4, zoom * Math.exp(-Math.max(-200, Math.min(200, pixels)) * .002)))
}

export function drawAvatarCrop(canvas: HTMLCanvasElement, image: HTMLImageElement, zoom: number, horizontal: number, vertical: number): void {
  const { x, y, size } = avatarCropRect(image.naturalWidth, image.naturalHeight, zoom, horizontal, vertical)
  const context = canvas.getContext('2d')
  if (!context) throw new Error('当前浏览器无法裁剪图片，请更换浏览器后重试。')
  canvas.width = AVATAR_OUTPUT_SIZE
  canvas.height = AVATAR_OUTPUT_SIZE
  context.clearRect(0, 0, canvas.width, canvas.height)
  context.imageSmoothingEnabled = true
  context.imageSmoothingQuality = 'high'
  context.drawImage(image, x, y, size, size, 0, 0, canvas.width, canvas.height)
}

export async function encodeAvatarCrop(canvas: HTMLCanvasElement): Promise<File> {
  const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(
    result => result ? resolve(result) : reject(new Error('裁剪图片生成失败，请重新选择图片。')), 'image/webp', .9,
  ))
  if (blob.type !== 'image/webp') throw new Error('当前浏览器不支持生成 WebP 图片，请更新浏览器后重试。')
  return new File([blob], 'avatar.webp', { type: 'image/webp' })
}
