// These are editable starting points, not an entitlement or free-quota list.
export const modelPresets = {
  qwen: { llm_api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', llm_model: 'qwen-plus', media_vision_model: 'qwen3-vl-plus', media_transcription_model: 'qwen3-asr-flash', media_transcription_protocol: 'qwen_asr' },
  'qwen-intl': { llm_api_base: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', llm_model: 'qwen-plus', media_vision_model: 'qwen3-vl-plus', media_transcription_model: 'qwen3-asr-flash', media_transcription_protocol: 'qwen_asr' },
  deepseek: { llm_api_base: 'https://api.deepseek.com/v1', llm_model: 'deepseek-chat', media_vision_model: '', media_transcription_model: '', media_transcription_protocol: 'openai' },
  openai: { llm_api_base: 'https://api.openai.com/v1', llm_model: 'gpt-4o-mini', media_vision_model: 'gpt-4o-mini', media_transcription_model: 'whisper-1', media_transcription_protocol: 'openai' },
} as const
export type ModelPreset = keyof typeof modelPresets

export function applyModelPreset(form: object, preset: ModelPreset) {
  // Deliberately retain entered credentials. Endpoint changes still require
  // explicit credential re-entry/clear at the backend before they can be saved.
  Object.assign(form, modelPresets[preset])
}
