<script setup lang="ts">
/**
 * InfoPulse — Login/Register Card
 * =================================
 * Glass card with tabs for login and registration.
 * Emits events on success; parent handles navigation.
 */
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const emit = defineEmits<{ success: [] }>()

const activeTab = ref<'login' | 'register'>('login')
const loading = ref(false)

// --- Login Form ---
const loginForm = reactive({ username: '', password: '' })

// --- Register Form ---
const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})

async function handleLogin() {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  loading.value = true
  try {
    await userStore.login(loginForm.username, loginForm.password)
    ElMessage.success('登录成功')
    emit('success')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!registerForm.username || !registerForm.email || !registerForm.password) {
    ElMessage.warning('请填写所有字段')
    return
  }
  if (registerForm.password !== registerForm.confirmPassword) {
    ElMessage.warning('两次密码不一致')
    return
  }
  if (registerForm.password.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }

  loading.value = true
  try {
    await userStore.register(
      registerForm.username,
      registerForm.email,
      registerForm.password,
    )
    ElMessage.success('注册成功')
    emit('success')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-card glass-card">
    <h2 class="card-title">InfoPulse</h2>
    <p class="card-subtitle">穿透信息迷雾，洞察真实情绪</p>

    <!-- Tabs -->
    <div class="tabs">
      <button
        :class="['tab', { active: activeTab === 'login' }]"
        @click="activeTab = 'login'"
      >
        登录
      </button>
      <button
        :class="['tab', { active: activeTab === 'register' }]"
        @click="activeTab = 'register'"
      >
        注册
      </button>
    </div>

    <!-- Login Form -->
    <form v-if="activeTab === 'login'" @submit.prevent="handleLogin" class="form">
      <el-input
        v-model="loginForm.username"
        placeholder="用户名或邮箱"
        size="large"
        clearable
      />
      <el-input
        v-model="loginForm.password"
        type="password"
        placeholder="密码"
        size="large"
        show-password
        clearable
      />
      <el-button
        type="primary"
        size="large"
        :loading="loading"
        class="submit-btn"
        @click="handleLogin"
      >
        登录
      </el-button>
    </form>

    <!-- Register Form -->
    <form v-if="activeTab === 'register'" @submit.prevent="handleRegister" class="form">
      <el-input
        v-model="registerForm.username"
        placeholder="用户名（至少3位）"
        size="large"
        clearable
      />
      <el-input
        v-model="registerForm.email"
        placeholder="邮箱地址"
        size="large"
        clearable
      />
      <el-input
        v-model="registerForm.password"
        type="password"
        placeholder="密码（至少6位）"
        size="large"
        show-password
      />
      <el-input
        v-model="registerForm.confirmPassword"
        type="password"
        placeholder="确认密码"
        size="large"
        show-password
      />
      <el-button
        type="primary"
        size="large"
        :loading="loading"
        class="submit-btn"
        @click="handleRegister"
      >
        注册
      </el-button>
    </form>
  </div>
</template>

<style scoped>
.login-card {
  width: 400px;
  padding: 40px;
  text-align: center;
}

.card-title {
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.card-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 8px 0 24px;
}

.tabs {
  display: flex;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 24px;
}

.tab {
  flex: 1;
  padding: 10px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 15px;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all var(--transition-fast);
}

.tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  font-weight: 600;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.submit-btn {
  margin-top: 8px;
}

@media (max-width: 480px) {
  .login-card {
    width: 90vw;
    padding: 24px;
  }
}
</style>
