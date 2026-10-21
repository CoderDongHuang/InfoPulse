import { ElMessage } from 'element-plus'
import { stage3Api } from '@/api/stage3'

export const RECENT_VIEW_RECORDED = 'infopulse:recent-view-recorded'

// Keep navigation usable if recording fails, but do not silently claim it was saved.
export async function recordRecentView(type: 'content' | 'event' | 'report' | 'history', id: string, title = '') {
  try {
    await stage3Api.recordView(type, id, title)
    window.dispatchEvent(new Event(RECENT_VIEW_RECORDED))
    return true
  } catch {
    ElMessage.warning('浏览记录未同步，请检查连接后重新打开内容。')
    return false
  }
}
