import request from './request'

export const automationApi = {
  templates: async () => (await request.get('/automation/templates')).data,
  subscriptions: async () => (await request.get('/subscriptions')).data,
  createSubscription: async (data: any) => (await request.post('/subscriptions', data)).data,
  toggleSubscription: async (id: string, enabled: boolean) => (await request.patch(`/subscriptions/${id}`, null, { params: { enabled } })).data,
  deleteSubscription: (id: string) => request.delete(`/subscriptions/${id}`),
  tasks: async () => (await request.get('/tasks')).data,
  createTask: async (data: any) => (await request.post('/tasks', data)).data,
  taskAction: async (id: string, action: 'pause'|'resume'|'cancel'|'confirm') => (await request.post(`/tasks/${id}/${action}`)).data,
  runTask: async (id: string) => (await request.post(`/tasks/${id}/run`)).data,
  runs: async (id: string) => (await request.get(`/tasks/${id}/runs`)).data,
  retryRun: async (id: string) => (await request.post(`/task-runs/${id}/retry`)).data,
  notifications: async (status?: string) => (await request.get('/notifications', { params: { status } })).data,
  unreadCount: async () => (await request.get('/notifications/unread-count')).data,
  markNotification: async (id: string, status: 'read'|'archived') => (await request.patch(`/notifications/${id}`, null, { params: { status } })).data,
  readAll: async () => (await request.post('/notifications/read-all')).data,
  preferences: async () => (await request.get('/notification-preferences')).data,
  updatePreferences: async (data: any) => (await request.patch('/notification-preferences', data)).data,
  deliveries: async () => (await request.get('/delivery-attempts')).data,
}
