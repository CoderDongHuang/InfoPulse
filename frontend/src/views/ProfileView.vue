<script setup lang="ts">
import { computed, onMounted, reactive, ref, shallowRef } from 'vue'
import axios from 'axios'
import { getApiError } from '@/api/request'
import { useUserStore } from '@/stores/user'
import UserAvatar from '@/components/layout/UserAvatar.vue'
import AvatarCropper from '@/components/common/AvatarCropper.vue'
import { validateAvatarSource } from '@/utils/avatarCrop'
import { profilePatch, validateAvatarFile, type ProfileFields } from '@/utils/profile'

const user = useUserStore()
const form = reactive<ProfileFields>({ username: '', email: '', avatar_url: '' })
const saved = ref<ProfileFields>({ ...form })
const loading = ref(true), ready = ref(false), saving = ref(false)
const error = ref(''), notice = ref('')
const avatarInput = ref<HTMLInputElement | null>(null), uploading = ref(false)
const avatarError = ref(''), avatarNotice = ref('')
const cropFile = shallowRef<File | null>(null)
const joined = computed(() => user.userInfo ? new Date(user.userInfo.created_at).toLocaleDateString('zh-CN') : '—')
const dirty = computed(() => Object.keys(form).some(key => form[key as keyof ProfileFields] !== saved.value[key as keyof ProfileFields]))

function reset() {
  Object.assign(form, saved.value)
  error.value = ''; notice.value = ''
}
async function load() {
  loading.value = true; error.value = ''
  try {
    await user.fetchUserInfo()
    if (!user.userInfo) throw new Error('Missing session')
    const { username, email, avatar_url } = user.userInfo
    saved.value = { username, email, avatar_url }; reset(); ready.value = true
  } catch { error.value = '无法读取个人资料，请检查连接后重试。'; ready.value = false }
  finally { loading.value = false }
}
async function save() {
  if (saving.value) return
  error.value = ''; notice.value = ''
  try {
    const patch = profilePatch(form, saved.value)
    if (!Object.keys(patch).length) { reset(); notice.value = '资料没有变化。'; return }
    saving.value = true
    const result = await user.updateProfile(patch)
    saved.value = { username: result.username, email: result.email, avatar_url: result.avatar_url }
    reset(); notice.value = '个人资料已保存。'
  } catch (cause) {
    if (axios.isAxiosError(cause)) {
      const status = cause.response?.status
      error.value = status === 409 ? '用户名或邮箱已被使用，请修改后重试。' : status === 422 ? '资料格式不正确，请检查用户名和邮箱。' : '保存失败，输入已保留，请检查连接后重试。'
    } else error.value = cause instanceof Error ? cause.message : '保存失败，请重试。'
  } finally { saving.value = false }
}
async function changeAvatar(file: File | null) {
  if (uploading.value || saving.value) return false
  avatarError.value = ''; avatarNotice.value = ''
  try {
    if (file) validateAvatarFile(file)
    uploading.value = true
    const result = await user.updateAvatar(file)
    saved.value.avatar_url = result.avatar_url; form.avatar_url = result.avatar_url
    avatarNotice.value = file ? '头像已上传并保存。' : '已恢复默认头像。'
    return true
  } catch (cause) {
    avatarError.value = axios.isAxiosError(cause) ? getApiError(cause).message : cause instanceof Error ? cause.message : '头像保存失败。'
    return false
  } finally { uploading.value = false; if (avatarInput.value) avatarInput.value.value = '' }
}
function selectAvatar(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  avatarError.value = ''; avatarNotice.value = ''
  try { validateAvatarSource(file); cropFile.value = file }
  catch (cause) { avatarError.value = cause instanceof Error ? cause.message : '图片读取失败。' }
}
async function uploadCrop(file: File) { if (await changeAvatar(file)) cropFile.value = null }
onMounted(load)
</script>
<template>
  <div class="page-shell profile-page">
    <header class="profile-heading"><p class="eyebrow">ACCOUNT / 个人空间</p><h1>个人中心</h1><p class="muted">管理个人资料与当前账户信息。</p></header>
    <p v-if="loading" role="status">正在读取个人资料…</p>
    <div v-else-if="!ready" class="surface profile-card"><p role="alert">{{ error }}</p><button class="primary" type="button" @click="load">重新加载</button></div>
    <div v-else class="profile-grid">
      <aside class="surface profile-card account-card">
        <UserAvatar :username="user.userInfo?.username" :url="user.userInfo?.avatar_url" />
        <h2>{{ user.userInfo?.username }}</h2><p>{{ user.userInfo?.email }}</p>
        <span class="account-tag">{{ user.userInfo?.is_admin ? '系统管理员' : '个人账户' }}</span>
        <dl><dt>加入时间</dt><dd>{{ joined }}</dd><dt>账户状态</dt><dd>{{ user.userInfo?.is_active ? '正常' : '已停用' }}</dd></dl>
        <router-link to="/reports">查看我的报告 →</router-link>
        <p><router-link to="/settings">私人配置：模型与邮件 →</router-link></p>
      </aside>
      <div class="profile-sections">
        <section class="surface profile-card" :aria-busy="uploading">
          <h2>头像</h2><p class="muted">从本地选择图片，调整裁剪区域并确认后上传，同步到右上角头像。</p>
          <label class="avatar-picker" for="profile-avatar">选择头像图片</label>
          <input id="profile-avatar" ref="avatarInput" type="file" accept="image/png,image/jpeg,image/webp" :disabled="uploading || saving" aria-describedby="avatar-help" @change="selectAvatar" />
          <small id="avatar-help">支持 PNG、JPEG、WebP；原图仅在本地裁剪，不按原图大小限制。确认后生成 512 × 512 WebP，校验不超过 2 MB 再上传；服务端保存为 256 × 256 WebP。</small>
          <div class="avatar-actions"><button class="secondary" type="button" :disabled="uploading || saving || !user.userInfo?.avatar_url" @click="changeAvatar(null)">恢复默认头像</button><span v-if="uploading" role="status">正在保存头像…</span></div>
          <p v-if="avatarError" class="form-error" role="alert">{{ avatarError }}</p><p v-if="avatarNotice" class="form-notice" role="status">{{ avatarNotice }}</p>
        </section>
        <form class="surface profile-card" @submit.prevent="save" :aria-busy="saving">
          <h2>基本资料</h2><p class="muted">资料仅在保存成功后更新。修改用户名后，请使用新用户名或邮箱登录。</p>
          <fieldset :disabled="saving || uploading">
            <label for="profile-username">用户名</label><input id="profile-username" v-model="form.username" autocomplete="username" required minlength="3" maxlength="50" aria-describedby="username-help" /><small id="username-help">3–50 个字符，新用户名不能包含 @。</small>
            <label for="profile-email">邮箱</label><input id="profile-email" v-model="form.email" type="email" autocomplete="email" required maxlength="100" />
          </fieldset>
          <p v-if="error" class="form-error" role="alert">{{ error }}</p><p v-if="notice" class="form-notice" role="status">{{ notice }}</p>
          <div class="form-actions"><button class="primary" type="submit" :disabled="saving || uploading || !dirty">{{ saving ? '保存中…' : '保存修改' }}</button><button class="secondary" type="button" :disabled="saving || uploading || !dirty" @click="reset">撤销修改</button></div>
        </form>
        <section class="surface profile-card session-card"><h2>会话与隐私</h2><p>登录凭证仅保存在当前浏览器标签页。需要退出时，可点击右上角头像 → 退出登录。</p><p class="muted">模型与邮件凭据在私人配置中按账号加密保存，其他账号无法读取。账户删除的跨存储一致性仍在验收中，本页暂不提供删除入口。</p></section>
      </div>
    </div>
    <AvatarCropper v-if="cropFile" :file="cropFile" :busy="uploading" :upload-error="avatarError" @cancel="cropFile = null" @confirm="uploadCrop" />
  </div>
</template>
<style scoped>
.avatar-picker{display:block}.avatar-actions{display:flex;align-items:center;gap:12px;margin-top:16px;font-size:13px}#avatar-help{display:block}
.profile-page { max-width: 1120px; padding-top: 36px; }.profile-heading { margin-bottom: 28px; }.profile-heading h1 { margin: 0; font-size: 30px; letter-spacing: -.8px; }.profile-heading > p:last-child { margin: 8px 0 0; font-size: 14px; }
.profile-grid { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 24px; align-items: start; }.profile-card { padding: 28px; box-shadow: none; }.profile-card h2 { margin: 0 0 8px; font-size: 18px; }.profile-card p { font-size: 13px; line-height: 1.8; }.account-card { text-align: center; overflow-wrap: anywhere; }.account-card :deep(.user-avatar) { width: 72px; height: 72px; font-size: 28px; margin-bottom: 18px; }.account-card > p { margin: 0 0 16px; color: var(--text-secondary); }.account-tag { display: inline-block; background: #eff4ff; color: #2453ae; border-radius: 5px; padding: 4px 10px; font-size: 11px; }
dl { display: grid; grid-template-columns: auto 1fr; gap: 12px; text-align: left; border-top: 1px solid var(--border-color); padding-top: 24px; margin: 24px 0; font-size: 12px; }dt { color: var(--text-secondary); }dd { margin: 0; text-align: right; }.account-card > a { color: var(--color-primary); font-size: 13px; }.profile-sections { display: grid; gap: 20px; }
fieldset { border: 0; padding: 0; margin: 24px 0; display: flex; flex-direction: column; }label { font-size: 13px; font-weight: 600; margin: 18px 0 8px; }label:first-child { margin-top: 0; }label span { color: var(--text-secondary); font-weight: 400; }input { width: 100%; padding: 11px 12px; border: 1px solid #cbd5e1; border-radius: 7px; background: #fff; color: var(--text-primary); font-size: 14px; }small { margin-top: 7px; font-size: 11px; line-height: 1.7; color: var(--text-secondary); }.form-actions { display: flex; gap: 10px; padding-top: 20px; border-top: 1px solid var(--border-color); }button { border-radius: 7px; min-height: 40px; padding: 0 18px; font-size: 13px; cursor: pointer; }.primary { background: #2563eb; color: #fff; border: 1px solid #2563eb; }.secondary { background: #fff; border: 1px solid #cbd5e1; color: #475569; }button:disabled { opacity: .5; cursor: not-allowed; }.form-error { color: #b91c1c; }.form-notice { color: #166534; }.session-card p { margin-bottom: 0; }
@media (max-width: 760px) { .profile-grid { grid-template-columns: 1fr; }.profile-card { padding: 22px; }.account-card { text-align: left; }.account-card :deep(.user-avatar) { width: 52px; height: 52px; font-size: 20px; } }
</style>
