import request from './request'

export interface SavedTarget {
  target_type: string; target_id: string; title: string; summary: string
  source_name: string; canonical_url: string | null; path: string | null; available: boolean
}
export interface WatchedTopicData { id: string; name: string; keywords: string[]; enabled: boolean; created_at: string }
export interface WorkspaceData {
  date: string
  attention: { id: string; name: string; count: number }[]
  recommendations: {
    id: string; title: string; summary: string; canonical_url: string
    recommendation_reasons: { rule: string; label: string }[]
  }[]
  favorites: SavedTarget[]
  followed_channels: { id: string; name: string }[]
  followed_items: WorkspaceData['recommendations']
  recent_views: (SavedTarget & { viewed_at: string })[]
  recent_reports: { id: string; title: string; report_type: string; status: string; updated_at: string; kind: string; path: string }[]
  source_warnings: { source_id: string | null; message: string }[]
}
export const stage3Api = {
  dashboard: async (days = 7) => (await request.get('/dashboard', { params: { days } })).data,
  discover: async (params: Record<string, unknown>) => (await request.get('/discover', { params })).data,
  channels: async () => (await request.get('/discover/channels')).data,
  follow: async (id: string) => (await request.post(`/discover/channels/${id}/follow`)).data,
  unfollow: async (id: string) => request.delete(`/discover/channels/${id}/follow`),
  feedback: async (id: string, feedback_type: string) => (await request.post(`/discover/items/${id}/feedback`, { feedback_type })).data,
  workspace: async (): Promise<WorkspaceData> => (await request.get('/workspace')).data,
  favorite: async (target_type: string, target_id: string) => (await request.post('/favorites', { target_type, target_id })).data,
  addTopic: async (name: string) => (await request.post('/watch-topics', { name, keywords: [], enabled: true })).data,
  topics: async (): Promise<WatchedTopicData[]> => (await request.get('/watch-topics')).data,
  removeTopic: async (id: string) => request.delete(`/watch-topics/${id}`),
  recordView: async (target_type: string, target_id: string, title: string) => (await request.post('/recent-views', { target_type, target_id, title })).data,
}
