import request from './request'
import { createSSEConnection, type SSECallbacks } from '@/utils/sse'
import { useUserStore } from '@/stores/user'

export type Platform = 'weibo' | 'bilibili' | 'tieba'

export interface InsightResult {
  history_id?: string
  topic: string
  overview: string
  sentiment: { positive: number; neutral: number; negative: number }
  confidence: number
  volume: number
  sources: { platform: string; count: number; status: string }[]
  key_points: { label: string; detail: string; stance: string }[]
  representative_opinions: { platform: string; content: string; stance: string; url: string }[]
  risks: string[]
  generated_at: string
}

export function analyzeInsight(data: { keyword: string; platforms: Platform[]; max_items: number }, callbacks: SSECallbacks) {
  const token = useUserStore().token
  return createSSEConnection('/api/v1/insights/analyze', {
    body: data,
    headers: { Authorization: `Bearer ${token}` },
    callbacks,
  })
}

export const workflowApi = {
  generateMouthpiece: async (data: Record<string, any>) => (await request.post('/mouthpiece/generate', data)).data,
  buildTimeline: async (data: Record<string, any>) => (await request.post('/timeline/build', data)).data,
  getHotRanking: async () => (await request.get('/hot-search/ranking', { headers: { 'X-Suppress-Error-Message': '1' } })).data,
  explainHotItem: async (data: Record<string, any>) => (await request.post('/hot-search/explain', data)).data,
  getHistory: async (module?: 'insight' | 'mouthpiece' | 'timeline') => (await request.get('/history', { params: { module } })).data,
  deleteHistory: async (id: string) => request.delete(`/history/${id}`),
}
