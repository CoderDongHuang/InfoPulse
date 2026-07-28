import request from './request'
export const stage3Api = {
  dashboard: async (days = 7) => (await request.get('/dashboard', { params: { days } })).data,
  discover: async (params: Record<string, unknown>) => (await request.get('/discover', { params })).data,
  channels: async () => (await request.get('/discover/channels')).data,
  follow: async (id: string) => (await request.post(`/discover/channels/${id}/follow`)).data,
  unfollow: async (id: string) => request.delete(`/discover/channels/${id}/follow`),
  feedback: async (id: string, feedback_type: string) => (await request.post(`/discover/items/${id}/feedback`, { feedback_type })).data,
  workspace: async () => (await request.get('/workspace')).data,
  favorite: async (target_type: string, target_id: string) => (await request.post('/favorites', { target_type, target_id })).data,
  addTopic: async (name: string) => (await request.post('/watch-topics', { name, keywords: [], enabled: true })).data,
  recordView: async (target_type: string, target_id: string, title: string) => (await request.post('/recent-views', { target_type, target_id, title })).data,
}
