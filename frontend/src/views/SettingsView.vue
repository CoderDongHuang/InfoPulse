<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import axios from 'axios'
import { readServiceSettings, saveServiceSettings, testService, type ServiceForm, type ServiceStatus } from '@/api/serviceSettings'

const form = reactive<ServiceForm>({ revision: 0, llm_api_base: 'https://api.openai.com/v1', llm_model: 'gpt-4o-mini', llm_api_key: '', media_vision_model: '', media_transcription_model: '', smtp_host: '', smtp_port: 587, smtp_username: '', smtp_password: '', smtp_from: '', clear_secrets: [] })
const status = ref<ServiceStatus>(), loading = ref(true), busy = ref(''), error = ref(''), notice = ref(''), baseline = ref('')
const dirty = computed(() => JSON.stringify(form) !== baseline.value)
const capabilities = computed(() => [
  { label: '公开资讯与检索', ready: true, text: '无需服务密钥' },
  { label: 'AI 对话与分析', ready: status.value?.capabilities.text_ai, text: '模型密钥、地址、文本模型' },
  { label: '图片理解', ready: status.value?.capabilities.vision && status.value?.capabilities.media_worker_enabled, text: '视觉模型与媒体工作进程' },
  { label: '音频转录', ready: status.value?.capabilities.transcription && status.value?.capabilities.media_worker_enabled, text: '转录模型与媒体工作进程' },
  { label: '邮件通知', ready: status.value?.capabilities.email, text: 'SMTP 服务与通知偏好' },
])
function accept(value: ServiceStatus) {
  status.value = value
  for (const key of ['revision', 'llm_api_base', 'llm_model', 'media_vision_model', 'media_transcription_model', 'smtp_host', 'smtp_port', 'smtp_username', 'smtp_from'] as const) Object.assign(form, { [key]: value[key] })
  form.llm_api_key = ''; form.smtp_password = ''; form.clear_secrets = []
  baseline.value = JSON.stringify(form)
}
async function load() {
  loading.value = true; error.value = ''; notice.value = ''
  try { accept((await readServiceSettings()).data) }
  catch { error.value = '无法读取配置。请检查服务连接与本机加密主密钥，然后重试。' }
  finally { loading.value = false }
}
async function save() {
  if (busy.value) return
  busy.value = 'save'; error.value = ''; notice.value = ''
  try { accept((await saveServiceSettings({ ...form, clear_secrets: [...form.clear_secrets] })).data); notice.value = '私人配置已加密保存，下次请求和后台任务将使用新配置。' }
  catch (cause) {
    const code = axios.isAxiosError(cause) ? cause.response?.status : 0
    error.value = code === 409 ? '配置已在其他标签页更新。请重新加载后再编辑。' : code === 503 ? '本机加密主密钥尚未配置或已变化，请联系实例管理员。' : code === 422 ? '配置格式不正确。请检查公开 HTTPS 地址、模型名称和邮箱；更换服务地址时必须重新输入或清除原密钥，不能同时替换和清除。' : '保存失败，输入已保留，请检查连接后重试。'
  } finally { busy.value = '' }
}
async function test(service: 'llm' | 'smtp') {
  if (busy.value || dirty.value) return
  busy.value = service; error.value = ''; notice.value = ''
  try { await testService(service); notice.value = service === 'llm' ? '模型已返回有效响应。此测试仅验证文本接口，不代表视觉／转录接口兼容。' : 'SMTP 加密连接与认证成功；没有发送邮件。' }
  catch { error.value = '连接测试未通过。请检查已保存的密钥、服务地址、模型权限、余额和网络。服务商返回内容已隐藏。' }
  finally { busy.value = '' }
}
function preset(value: string) {
  if (value === 'deepseek') { form.llm_api_base = 'https://api.deepseek.com/v1'; form.llm_model = 'deepseek-chat' }
  if (value === 'openai') { form.llm_api_base = 'https://api.openai.com/v1'; form.llm_model = 'gpt-4o-mini' }
}
onMounted(load)
</script>

<template>
  <div class="page-shell settings-page">
    <header class="settings-heading"><p class="eyebrow">PREFERENCES / 私人配置</p><h1>连接你的服务</h1><p class="muted">每个账号使用自己的模型和邮件服务，按需开启能力。</p></header>
    <p v-if="loading" role="status">正在读取配置…</p>
    <div v-else-if="!status" class="surface settings-card"><p role="alert">{{ error }}</p><button type="button" @click="load">重新加载</button></div>
    <template v-else>
      <section class="privacy-note"><el-icon aria-hidden="true"><Lock /></el-icon><div><strong>仅当前账号使用</strong><p>密钥加密存储在本机后端数据库，不回显、不存入浏览器缓存、不上传到项目仓库。调用服务时，会向你指定的服务商发送必要的文本或文件。实例管理员能管理服务器与加密密钥，请仅在你信任的实例上配置。</p></div></section>
      <p v-if="!status.encryption_ready" class="form-error" role="alert">实例管理员需先设置独立的 PLATFORM_ENCRYPTION_KEY（至少 32 字符）；本地公开数据启动器会自动生成。</p>
      <section class="capability-grid" aria-label="已保存配置的能力状态"><article v-for="item in capabilities" :key="item.label" class="surface capability"><span :class="{ ready: item.ready }">{{ item.ready ? '已配置' : '待配置' }}</span><h2>{{ item.label }}</h2><p>{{ item.text }}</p></article></section>
      <p class="status-help muted">状态按已保存字段判断，尚不代表服务商连通或余额充足。请保存后测试，并运行对应功能验收。</p>
      <form @submit.prevent="save" :aria-busy="!!busy">
        <fieldset :disabled="!!busy || !status.encryption_ready">
          <section class="surface settings-card">
            <div class="section-title"><el-icon aria-hidden="true"><ChatDotRound /></el-icon><div><h2>AI 模型</h2><p>支持 OpenAI 兼容接口。配置后用于对话、分析、报告改写与翻译；编排仍需设置模型路由和预算。</p></div></div>
            <div class="presets"><span>快速填写</span><button type="button" @click="preset('deepseek')">DeepSeek</button><button type="button" @click="preset('openai')">OpenAI</button><span>也可手动填写其他兼容服务</span></div>
            <div class="fields">
              <label class="wide" for="llm-base">API 基础地址<input id="llm-base" v-model="form.llm_api_base" type="url" required maxlength="500" placeholder="https://api.example.com/v1" /><small>仅支持公开 HTTPS 的标准端口，不允许本机、内网、查询参数或携带用户名密码。更换地址需重新输入或清除原密钥。</small></label>
              <label for="llm-model">文本模型<input id="llm-model" v-model="form.llm_model" required maxlength="150" placeholder="deepseek-chat" /></label>
              <label for="llm-key"><span class="field-heading">API Key <small>{{ status.llm_api_key_configured ? '已保存 · 留空保留' : '尚未配置' }}</small></span><input id="llm-key" v-model="form.llm_api_key" type="password" autocomplete="new-password" maxlength="4096" placeholder="输入你自己的服务密钥" /></label>
              <label class="check wide"><input v-model="form.clear_secrets" type="checkbox" value="llm_api_key" />清除已保存的模型密钥（关闭模型调用）</label>
              <label for="vision-model">视觉模型（可选）<input id="vision-model" v-model="form.media_vision_model" maxlength="150" placeholder="填写服务商支持的图片理解模型" /></label>
              <label for="audio-model">转录模型（可选）<input id="audio-model" v-model="form.media_transcription_model" maxlength="150" placeholder="填写支持带时间戳转录的模型" /></label>
            </div>
            <p class="hint">视觉与音频共用上面的服务地址和密钥；纯文本服务不一定支持图片或转录。视频还需要 FFmpeg / ffprobe。{{ status.capabilities.media_worker_enabled ? '媒体工作进程已启用。' : '当前实例未启用媒体工作进程，请由管理员开启后使用。' }}</p>
            <button class="secondary" type="button" :disabled="!!busy || dirty || !status.llm_api_key_configured" @click="test('llm')">{{ busy === 'llm' ? '模型测试中…' : '测试已保存的文本模型' }}</button><small class="test-note">会向服务商发起一次少量 token 的真实请求，可能计费。</small>
          </section>
          <section class="surface settings-card">
            <div class="section-title"><el-icon aria-hidden="true"><Message /></el-icon><div><h2>邮件服务</h2><p>配置你自己的 SMTP 服务，再到通知中心开启邮件通知、填写接收地址。</p></div></div>
            <div class="fields">
              <label for="smtp-host">SMTP 主机<input id="smtp-host" v-model="form.smtp_host" maxlength="253" placeholder="smtp.example.com" /></label>
              <label for="smtp-port">加密连接<select id="smtp-port" v-model="form.smtp_port"><option :value="587">587 · STARTTLS</option><option :value="465">465 · TLS</option></select></label>
              <label for="smtp-user">SMTP 用户名<input id="smtp-user" v-model="form.smtp_username" maxlength="254" autocomplete="off" placeholder="服务商提供的用户名" /></label>
              <label for="smtp-password"><span class="field-heading">SMTP 密码／授权码 <small>{{ status.smtp_password_configured ? '已保存 · 留空保留' : '尚未配置' }}</small></span><input id="smtp-password" v-model="form.smtp_password" type="password" autocomplete="new-password" maxlength="4096" /></label>
              <label class="wide" for="smtp-from">已验证的发件邮箱<input id="smtp-from" v-model="form.smtp_from" type="email" maxlength="254" placeholder="reports@example.com" /></label>
              <label class="check wide"><input v-model="form.clear_secrets" type="checkbox" value="smtp_password" />清除已保存的 SMTP 密码</label>
            </div>
            <button class="secondary" type="button" :disabled="!!busy || dirty || !status.capabilities.email" @click="test('smtp')">{{ busy === 'smtp' ? '邮件连接测试中…' : '测试已保存的邮件连接' }}</button><small class="test-note">验证 TLS 连接和认证，不发送邮件。<router-link to="/notifications">打开通知中心 →</router-link></small>
          </section>
        </fieldset>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p><p v-if="notice" class="form-notice" role="status">{{ notice }}</p>
        <div class="settings-actions"><button class="primary" type="submit" :disabled="!!busy || !dirty || !status.encryption_ready">{{ busy === 'save' ? '保存中…' : '保存私人配置' }}</button><button class="secondary" type="button" :disabled="!!busy" @click="load">重新加载已保存配置</button><span class="muted">{{ dirty ? '有未保存的修改，请先保存再测试' : '密钥不回显，留空保留原值' }}</span></div>
      </form>
      <section class="surface settings-card more-settings"><h2>其他能力需要什么？</h2><dl><dt>公开资讯、检索、收藏、证据摘要、知识库</dt><dd>无需模型密钥。采集需要网络；文档解析与后台任务需要工作进程运行。</dd><dt>视频理解</dt><dd>在同一模型服务配置视觉与音频模型，安装 FFmpeg / ffprobe，开启媒体工作进程。</dd><dt>Webhook 通知</dt><dd>到通知中心配置你控制的公开 HTTPS 接收地址与签名密钥。</dd><dt>共享平台数据源、企业 SSO、S3 存储</dt><dd>由实例管理员在数据源／企业治理／本机环境配置。共享采集不会使用你的私人账号 Cookie。</dd><dt>支付、保险、清算、跨机构联邦等实验模块</dt><dd>仍需真实业务适配器、外部机构和独立验收。填写服务密钥不能将其变成可用的生产服务。</dd></dl><p class="muted">详细配置清单见仓库 docs/29-configuration-guide.md。无需把密钥发给项目作者。</p></section>
    </template>
  </div>
</template>

<style scoped>
.settings-page{max-width:1120px;padding-top:36px;padding-bottom:40px}.settings-heading{margin-bottom:24px}.settings-heading h1{margin:0;font-size:30px;letter-spacing:-.7px}.settings-heading>p:last-child{font-size:14px;margin-top:10px}.privacy-note{display:flex;gap:14px;padding:20px 24px;border:1px solid #dbe6f4;background:#f5f8fd;border-radius:12px;margin:24px 0}.privacy-note>.el-icon{font-size:22px;color:#2563eb;margin-top:2px;flex-shrink:0}.privacy-note strong{font-size:14px}.privacy-note p{margin:6px 0 0;font-size:12px;line-height:1.8;color:#52637a}.capability-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.capability{padding:18px;box-shadow:none}.capability span{font-size:11px;color:#64748b}.capability .ready{color:#166534}.capability h2{font-size:14px;margin:10px 0 7px}.capability p{font-size:11px;color:var(--text-secondary);line-height:1.6;margin:0}.status-help{font-size:12px;margin:12px 0 24px}.settings-card{padding:28px;margin-bottom:20px;box-shadow:none}.settings-card h2{font-size:18px;margin:0}.section-title{display:flex;gap:12px;margin-bottom:24px}.section-title>.el-icon{font-size:22px;color:#2563eb;flex-shrink:0}.section-title p{margin:7px 0 0;color:var(--text-secondary);font-size:12px;line-height:1.7}.presets{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:22px;font-size:12px;color:#64748b}.presets button{min-height:32px;background:#f8fafc;border:1px solid #dbe3ee;color:#334155;padding:0 12px}.fields{display:grid;grid-template-columns:1fr 1fr;gap:22px 24px}fieldset{border:0;margin:0;padding:0;min-width:0}label{display:flex;flex-direction:column;gap:8px;font-size:13px;font-weight:600;min-width:0}label span{font-size:11px;font-weight:400;color:#64748b}.wide{grid-column:1/-1}input:not([type=checkbox]),select{width:100%;min-height:42px;border:1px solid #cbd5e1;border-radius:7px;padding:10px 12px;background:#fff;color:var(--text-primary);font:inherit;font-weight:400}small{font-size:11px;line-height:1.7;color:#64748b;font-weight:400}.check{flex-direction:row;align-items:center;font-weight:400}.check input{accent-color:#2563eb;width:16px;height:16px}.hint{font-size:12px;line-height:1.8;color:#64748b;margin:22px 0}.test-note{display:inline-block;margin:10px 0 0 12px}.test-note a{color:#2563eb;margin-left:8px}button{min-height:40px;padding:0 17px;border-radius:7px;cursor:pointer;font-size:13px}.primary{background:#2563eb;color:white;border:1px solid #2563eb}.secondary{background:#fff;color:#475569;border:1px solid #cbd5e1}button:disabled{opacity:.5;cursor:not-allowed}.settings-actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:22px 0 28px}.settings-actions span{font-size:12px}.form-error{color:#b91c1c;font-size:13px;line-height:1.8}.form-notice{color:#166534;font-size:13px;line-height:1.8}.more-settings dl{margin:24px 0;display:grid;grid-template-columns:minmax(180px,1fr) 2fr;gap:18px 28px;font-size:13px;line-height:1.8}.more-settings dt{font-weight:600}.more-settings dd{margin:0;color:#64748b}.more-settings>p{font-size:12px}@media(max-width:850px){.capability-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:600px){.fields{grid-template-columns:1fr}.settings-card{padding:20px}.capability-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.more-settings dl{grid-template-columns:1fr;gap:8px}.more-settings dd{margin-bottom:14px}.test-note{display:block;margin-left:0}.privacy-note{padding:18px}.settings-actions{align-items:stretch}.settings-heading h1{font-size:27px}}
</style>

<style scoped>
.fields { align-items: end; }
.fields label { line-height: 20px; }
.fields .field-heading { display: flex; align-items: baseline; flex-wrap: wrap; gap: 0 10px; font-size: inherit; font-weight: inherit; color: inherit; }
.field-heading small { line-height: inherit; }
.fields input:not([type=checkbox]), .fields select { box-sizing: border-box; height: 44px; }
</style>
