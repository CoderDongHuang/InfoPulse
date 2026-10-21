import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const source = readFileSync(new URL('../src/utils/modelPresets.ts', import.meta.url), 'utf8')
const context = { exports: {} }
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context)
const { applyModelPreset } = context.exports

test('Qwen selects region and corresponding capabilities while preserving account credentials', () => {
  const form = { revision: 4, llm_api_key: 'private', smtp_password: 'mail' }
  applyModelPreset(form, 'qwen')
  assert.equal(form.llm_model, 'qwen-plus')
  assert.equal(form.media_vision_model, 'qwen3-vl-plus')
  assert.equal(form.media_transcription_model, 'qwen3-asr-flash')
  assert.equal(form.media_transcription_protocol, 'qwen_asr')
  applyModelPreset(form, 'qwen-intl')
  assert.equal(form.llm_api_base, 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1')
  assert.equal(form.llm_api_key, 'private')
  assert.equal(form.smtp_password, 'mail')
  assert.equal(form.revision, 4)
})

test('switching from Qwen to a text-only provider clears incompatible media defaults', () => {
  const form = {}
  applyModelPreset(form, 'qwen')
  applyModelPreset(form, 'deepseek')
  assert.equal(form.llm_model, 'deepseek-chat')
  assert.equal(form.media_vision_model, '')
  assert.equal(form.media_transcription_model, '')
  assert.equal(form.media_transcription_protocol, 'openai')
  applyModelPreset(form, 'openai')
  assert.equal(form.media_transcription_model, 'whisper-1')
})
