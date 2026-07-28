import request from './request'

export interface SearchItem {
  id: string; title: string; summary: string; source: { id: string; key: string; name: string }
  author: string; published_at: string | null; heat: number; sentiment: string; tags: string[]
  event: { id: string } | null; canonical_url: string; content_type: string; language: string; region: string
  is_original: boolean | null; is_official: boolean
}
export interface Page<T> { items: T[]; page: number; page_size: number; total: number; has_more: boolean }
export interface SavedSearch { id: string; name: string; query: string; filters: Record<string, unknown>; created_at: string; updated_at: string }
export interface IntelligenceEvent {
  id: string; title: string; summary: string; category: string; status: string; heat_score: number; risk_score: number
  confidence: number; started_at: string | null; ended_at: string | null; last_activity_at: string | null
  updated_at: string; content_count: number; source_count: number; manual_locked: boolean
  entities?: { name: string; type: string; mention_count: number }[]; risk_notes?: string
}

export const intelligenceApi = {
  search: async (params: Record<string, unknown>) => (await request.get<Page<SearchItem>>('/search', { params })).data,
  content: async (id: string) => (await request.get(`/contents/${id}`)).data,
  savedSearches: async () => (await request.get<SavedSearch[]>('/saved-searches')).data,
  saveSearch: async (data: { name: string; query: string; filters: Record<string, unknown> }) => (await request.post<SavedSearch>('/saved-searches', data)).data,
  deleteSavedSearch: async (id: string) => request.delete(`/saved-searches/${id}`),
  events: async (params: Record<string, unknown>) => (await request.get<Page<IntelligenceEvent>>('/events', { params })).data,
  event: async (id: string) => (await request.get<IntelligenceEvent>(`/events/${id}`)).data,
  createEvent: async (data: { title: string; category: string; content_ids: string[] }) => (await request.post<IntelligenceEvent>('/events', data)).data,
  updateEvent: async (id: string, data: Record<string, unknown>) => (await request.patch<IntelligenceEvent>(`/events/${id}`, data)).data,
  mergeEvents: async (data: { target_event_id: string; source_event_ids: string[]; keep_title?: string }) => (await request.post<IntelligenceEvent>('/events/merge', data)).data,
  clusterEvents: async () => (await request.post<{ scanned_count: number; created_count: number; event_ids: string[] }>('/events/cluster', {})).data,
  timeline: async (id: string) => (await request.get(`/events/${id}/timeline`)).data,
  eventSources: async (id: string) => (await request.get(`/events/${id}/sources`)).data,
  audits: async (id: string) => (await request.get(`/events/${id}/audit-logs`)).data,
}
