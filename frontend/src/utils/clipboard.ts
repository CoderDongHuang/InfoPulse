/**
 * InfoPulse — Clipboard Utility
 * ==============================
 * Copy text to the system clipboard with Toast feedback.
 */

import { ElMessage } from 'element-plus'

export async function copyToClipboard(text: string, label?: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success(label ? `${label}已复制到剪贴板` : '已复制到剪贴板')
    return true
  } catch {
    // Fallback for older browsers
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    try {
      document.execCommand('copy')
      ElMessage.success('已复制到剪贴板')
      return true
    } catch {
      ElMessage.error('复制失败，请手动复制')
      return false
    } finally {
      document.body.removeChild(textarea)
    }
  }
}
