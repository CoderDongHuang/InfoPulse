import request from './request'

export interface DataSource {
  id: string; key: string; name: string; source_type: 'official_api' | 'rss'; base_url: string
  enabled: boolean; health_status: 'unknown' | 'healthy' | 'error'; sync_interval_minutes: number
  last_sync_at: string | null; last_success_at: string | null; last_error: string | null
}

export interface SyncRun {
  id: string; source_id: string; trigger_type: string; status: 'running' | 'succeeded' | 'failed'
  started_at: string | null; finished_at: string | null; fetched_count: number; created_count: number
  updated_count: number; skipped_count: number; error_count: number; error_summary: string | null
  diagnostic_id: string | null; created_at: string
}

export interface ConnectionResult { status: 'healthy' | 'error'; item_count: number; message: string; checked_at: string }

export const sourceApi = {
  list: async () => (await request.get<DataSource[]>('/sources')).data,
  update: async (id: string, data: { enabled?: boolean; sync_interval_minutes?: number }) => (await request.patch<DataSource>(`/sources/${id}`, data)).data,
  test: async (id: string) => (await request.post<ConnectionResult>(`/sources/${id}/test`)).data,
  sync: async (id: string) => (await request.post<SyncRun>(`/sources/${id}/sync`)).data,
  runs: async (id: string) => (await request.get<SyncRun[]>(`/sources/${id}/sync-runs`)).data,
  validateRss: async (feed_url: string) => (await request.post<ConnectionResult>('/sources/rss/validate', { feed_url })).data,
  addRss: async (data: { name: string; feed_url: string; sync_interval_minutes: number }) => (await request.post<DataSource>('/sources/rss', data)).data,
  remove: async (id: string) => request.delete(`/sources/${id}`),
}
