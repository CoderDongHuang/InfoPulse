import request from './request'

export interface ServiceForm {
  revision: number
  llm_api_base: string
  llm_model: string
  llm_api_key: string
  media_vision_model: string
  media_transcription_model: string
  media_transcription_protocol: 'openai' | 'qwen_asr'
  smtp_host: string
  smtp_port: 465 | 587
  smtp_username: string
  smtp_password: string
  smtp_from: string
  clear_secrets: ('llm_api_key' | 'smtp_password')[]
}
export interface ServiceStatus extends Omit<ServiceForm, 'llm_api_key' | 'smtp_password' | 'clear_secrets'> {
  encryption_ready: boolean
  llm_api_key_configured: boolean
  smtp_password_configured: boolean
  capabilities: { public_data: boolean; text_ai: boolean; vision: boolean; transcription: boolean; email: boolean; media_worker_enabled: boolean }
}
const options = { headers: { 'X-Suppress-Error-Message': 'true' } }
export const readServiceSettings = () => request.get<ServiceStatus>('/settings/services', options)
export const saveServiceSettings = (form: ServiceForm) => request.put<ServiceStatus>('/settings/services', form, options)
export const testService = (service: 'llm' | 'smtp') => request.post(`/settings/services/test/${service}`, null, options)
