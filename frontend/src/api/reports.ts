import request from './request'

export type ReportType = 'daily' | 'weekly' | 'event' | 'industry' | 'executive' | 'risk'
export type ExportFormat = 'markdown' | 'html' | 'docx' | 'pdf'

export const reportsApi = {
  templates: async () => (await request.get('/report-templates')).data,
  list: async () => (await request.get('/reports')).data,
  create: async (data: { title: string; report_type: ReportType; source_config?: Record<string, unknown> }) => (await request.post('/reports', data)).data,
  detail: async (id: string) => (await request.get(`/reports/${id}`)).data,
  update: async (id: string, data: { title?: string; status?: string }) => (await request.patch(`/reports/${id}`, data)).data,
  remove: (id: string) => request.delete(`/reports/${id}`),
  versions: async (id: string) => (await request.get(`/reports/${id}/versions`)).data,
  saveVersion: async (id: string, data: { content_markdown: string; structured_content: Record<string, unknown>; citation_content_ids: string[] }) => (await request.post(`/reports/${id}/versions`, data)).data,
  restore: async (id: string, versionId: string) => (await request.post(`/reports/${id}/versions/${versionId}/restore`)).data,
  rewrite: async (id: string, selected_text: string, instruction: string) => (await request.post(`/reports/${id}/rewrite`, { selected_text, instruction })).data,
  export: async (id: string, format: ExportFormat) => (await request.post(`/reports/${id}/exports`, { format })).data,
  retry: async (exportId: string) => (await request.post(`/report-exports/${exportId}/retry`)).data,
  downloadUrl: (exportId: string) => `/api/v1/report-exports/${exportId}/download`,
}
