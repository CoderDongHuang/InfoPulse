<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { Key, Lock, Message, User } from '@element-plus/icons-vue'

const userStore = useUserStore()
const emit = defineEmits<{ success: [] }>()
const mode = ref<'login' | 'register'>('login')
const loading = ref(false)
const form = reactive({ username: '', email: '', password: '', confirm: '' })
const passwordStrength = computed(() => {
  let score = 0
  if (form.password.length >= 8) score++
  if (/[A-Za-z]/.test(form.password) && /\d/.test(form.password)) score++
  if (/[^A-Za-z0-9]/.test(form.password)) score++
  return score
})

async function submit() {
  const username = form.username.trim()
  const email = form.email.trim()
  if (!username || !form.password) return ElMessage.warning('请填写账号和密码')
  if (mode.value === 'register' && username.length < 3) return ElMessage.warning('用户名至少 3 个字符')
  if (form.password.length < 6) return ElMessage.warning('密码至少 6 位')
  if (mode.value === 'register' && !/^\S+@\S+\.\S+$/.test(email)) return ElMessage.warning('请输入有效邮箱')
  if (mode.value === 'register' && form.password !== form.confirm) return ElMessage.warning('两次输入的密码不一致')
  loading.value = true
  try {
    if (mode.value === 'login') await userStore.login(username, form.password)
    else await userStore.register(username, email, form.password)
    ElMessage.success(mode.value === 'login' ? '已进入工作台' : '账号已创建')
    emit('success')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '操作失败，请重试')
  } finally { loading.value = false }
}
</script>

<template>
  <div class="auth-card">
    <div class="mode-switch">
      <button type="button" :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
      <button type="button" :class="{ active: mode === 'register' }" @click="mode = 'register'">创建账号</button>
    </div>
    <header>
      <p>{{ mode === 'login' ? 'WELCOME BACK' : 'NEW WORKSPACE' }}</p>
      <h2>{{ mode === 'login' ? '继续你的舆情工作' : '建立个人舆情工作区' }}</h2>
    </header>
    <form @submit.prevent="submit">
      <label><span>账号</span><el-input v-model="form.username" size="large" placeholder="用户名或邮箱" :prefix-icon="User" /></label>
      <label v-if="mode === 'register'"><span>邮箱</span><el-input v-model="form.email" size="large" placeholder="name@example.com" :prefix-icon="Message" /></label>
      <label><span>密码</span><el-input v-model="form.password" size="large" type="password" show-password placeholder="至少 6 位" :prefix-icon="Lock" /></label>
      <div v-if="mode === 'register'" class="password-strength" :class="`level-${passwordStrength}`"><i></i><i></i><i></i><span>{{ ['请设置密码', '基础', '可靠', '较强'][passwordStrength] }}</span></div>
      <label v-if="mode === 'register'"><span>确认密码</span><el-input v-model="form.confirm" size="large" type="password" show-password placeholder="再次输入密码" :prefix-icon="Key" /></label>
      <button class="submit" type="submit" :disabled="loading"><span>{{ loading ? '正在验证' : mode === 'login' ? '进入工作台' : '创建并进入' }}</span><el-icon><Right /></el-icon></button>
    </form>
    <div class="trust-row"><span>会话级 Token</span><span>密码哈希存储</span><span>私有历史记录</span></div>
  </div>
</template>

<style scoped>
.auth-card { width: min(100%, 430px); }
.mode-switch { position: relative; display: grid; grid-template-columns: 1fr 1fr; width: 100%; padding: 4px; border: 1px solid #d4ded9; background: #edf3f0; border-radius: 7px; }
.mode-switch button { position: relative; z-index: 1; min-height: 38px; padding: 0 14px; border: 0; background: transparent; border-radius: 4px; color: #6d817a; cursor: pointer; transition: color 160ms ease, background 160ms ease, box-shadow 160ms ease; }
.mode-switch button.active { background: white; color: #14231f; box-shadow: 0 5px 14px rgba(22,48,40,.08); font-weight: 700; }
header { margin: 32px 0 28px; }
header p { margin: 0 0 9px; color: #1f8178; font: 750 10px/1.2 "Cascadia Code", monospace; letter-spacing: .12em; }
header h2 { margin: 0; font: 650 30px/1.25 Georgia, "Songti SC", serif; }
form { display: grid; gap: 16px; }
label { display: grid; gap: 7px; }
label > span { color: #334b44; font-size: 11px; font-weight: 700; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 5px; box-shadow: 0 0 0 1px #cbd7d2 inset; background: rgba(255,255,255,.82); transition: box-shadow 160ms ease, background 160ms ease; }:deep(.el-input__wrapper:hover) { box-shadow: 0 0 0 1px #8eaaa1 inset; }:deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px #1f8178 inset, 0 0 0 4px rgba(31,129,120,.1); background: white; }
.password-strength { margin-top: -8px; display: grid; grid-template-columns: repeat(3, 1fr) auto; gap: 5px; align-items: center; }.password-strength i { height: 3px; border-radius: 2px; background: #dae2de; }.password-strength span { margin-left: 4px; color: #84958f; font-size: 9px; }.password-strength.level-1 i:nth-child(1) { background: #df625b; }.password-strength.level-2 i:nth-child(-n+2) { background: #d9a83a; }.password-strength.level-3 i { background: #1f9d69; }
.submit { margin-top: 7px; min-height: 50px; padding: 0 18px; border: 0; border-radius: 5px; background: #14231f; color: white; display: flex; align-items: center; justify-content: space-between; cursor: pointer; box-shadow: 0 10px 22px rgba(20,35,31,.16); transition: transform 160ms ease, background 160ms ease, box-shadow 160ms ease; }
.submit:hover { transform: translateY(-2px); background: #167f76; box-shadow: 0 14px 28px rgba(22,127,118,.2); }
.submit:disabled { opacity: .6; cursor: wait; }
.trust-row { margin-top: 26px; padding-top: 18px; border-top: 1px solid #dfe7e3; display: flex; gap: 14px; flex-wrap: wrap; color: #81938c; font-size: 9px; }
.trust-row span::before { content: ''; display: inline-block; width: 5px; height: 5px; margin-right: 6px; border-radius: 50%; background: #27a171; }
</style>
