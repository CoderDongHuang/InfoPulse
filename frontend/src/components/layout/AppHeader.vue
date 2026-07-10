<script setup lang="ts">
/**
 * InfoPulse — App Header / Navigation Bar
 * ========================================
 * Three-section layout: Logo | Nav Menu | User Area
 * Responsive: collapses to hamburger menu below 768px.
 */
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const appStore = useAppStore()

const mobileMenuOpen = ref(false)

// --- Navigation Items ---
interface NavItem {
  path: string
  title: string
  children?: { path: string; title: string }[]
}

const navItems: NavItem[] = [
  {
    path: '/',
    title: '首页',
    children: [
      { path: '/', title: '产品介绍' },
      { path: '/', title: '使用指南' },
      { path: '/', title: '案例展示' },
    ],
  },
  {
    path: '/anti-scam',
    title: '避坑雷达',
    children: [
      { path: '/anti-scam', title: '商品评测' },
      { path: '/anti-scam', title: '品牌对比' },
      { path: '/anti-scam', title: '风险预警' },
    ],
  },
  {
    path: '/mouthpiece',
    title: '嘴替生成',
    children: [
      { path: '/mouthpiece', title: '职场吐槽' },
      { path: '/mouthpiece', title: '情感分享' },
      { path: '/mouthpiece', title: '生活趣事' },
    ],
  },
  {
    path: '/timeline',
    title: '吃瓜时间线',
    children: [
      { path: '/timeline', title: '热点追踪' },
      { path: '/timeline', title: '事件回顾' },
      { path: '/timeline', title: '趋势分析' },
    ],
  },
]

const isActive = (path: string) => route.path === path

// --- User Menu ---
function handleUserCommand(command: string) {
  switch (command) {
    case 'profile':
      ElMessage.info('个人中心（开发中）')
      break
    case 'history':
      ElMessage.info('历史记录（开发中）')
      break
    case 'settings':
      ElMessage.info('设置（开发中）')
      break
    case 'theme':
      appStore.toggleTheme()
      break
    case 'logout':
      userStore.logout()
      router.push('/auth')
      ElMessage.success('已退出登录')
      break
  }
}

function goToAuth() {
  router.push('/auth')
}
</script>

<template>
  <header class="app-header glass-card">
    <!-- Left: Logo -->
    <div class="header-left">
      <router-link to="/" class="logo-link">
        <div class="logo-icon">📡</div>
        <span class="logo-text">InfoPulse</span>
      </router-link>
    </div>

    <!-- Center: Navigation (desktop) -->
    <nav class="header-nav desktop-nav">
      <div
        v-for="item in navItems"
        :key="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
      >
        <router-link :to="item.path" class="nav-link">
          {{ item.title }}
        </router-link>
        <!-- Dropdown -->
        <div v-if="item.children" class="nav-dropdown glass-card">
          <router-link
            v-for="child in item.children"
            :key="child.title"
            :to="child.path"
            class="dropdown-item"
          >
            {{ child.title }}
          </router-link>
        </div>
      </div>
    </nav>

    <!-- Right: User Area -->
    <div class="header-right">
      <!-- Not Logged In -->
      <template v-if="!userStore.isLoggedIn">
        <el-button size="small" @click="goToAuth">登录</el-button>
        <el-button size="small" type="primary" @click="goToAuth">注册</el-button>
      </template>

      <!-- Logged In -->
      <template v-else>
        <el-badge :value="0" :max="99" class="notification-badge">
          <el-icon :size="20"><Bell /></el-icon>
        </el-badge>

        <el-dropdown @command="handleUserCommand" trigger="click">
          <div class="user-avatar-area">
            <el-avatar :size="32" :src="userStore.userInfo?.avatar_url">
              {{ userStore.userInfo?.username?.charAt(0)?.toUpperCase() || 'U' }}
            </el-avatar>
            <span class="username">{{ userStore.userInfo?.username }}</span>
            <el-icon class="arrow-icon"><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">
                <el-icon><User /></el-icon> 个人中心
              </el-dropdown-item>
              <el-dropdown-item command="history">
                <el-icon><Clock /></el-icon> 历史记录
              </el-dropdown-item>
              <el-dropdown-item command="settings">
                <el-icon><Setting /></el-icon> 设置偏好
              </el-dropdown-item>
              <el-dropdown-item command="theme">
                <el-icon><Moon /></el-icon>
                {{ appStore.theme === 'light' ? '暗黑模式' : '明亮模式' }}
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided>
                <el-icon><SwitchButton /></el-icon> 退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>

      <!-- Hamburger (mobile) -->
      <el-button
        class="hamburger-btn"
        :icon="mobileMenuOpen ? 'Close' : 'Menu'"
        circle
        @click="mobileMenuOpen = !mobileMenuOpen"
      />
    </div>
  </header>

  <!-- Mobile Drawer Menu -->
  <el-drawer
    v-model="mobileMenuOpen"
    direction="ltr"
    size="70%"
    title="InfoPulse"
    :with-header="true"
  >
    <nav class="mobile-nav">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="mobile-nav-item"
        :class="{ active: isActive(item.path) }"
        @click="mobileMenuOpen = false"
      >
        {{ item.title }}
      </router-link>

      <el-divider />

      <template v-if="!userStore.isLoggedIn">
        <el-button type="primary" block @click="goToAuth(); mobileMenuOpen = false">
          登录 / 注册
        </el-button>
      </template>
      <template v-else>
        <div class="mobile-nav-item" @click="handleUserCommand('logout'); mobileMenuOpen = false">
          退出登录
        </div>
      </template>
    </nav>
  </el-drawer>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 60px;
  position: sticky;
  top: 0;
  z-index: 1000;
  border-radius: 0;
  border-top: none;
  border-left: none;
  border-right: none;
  background: var(--bg-card);
  backdrop-filter: blur(12px);
}

/* --- Left --- */
.header-left {
  flex-shrink: 0;
}

.logo-link {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  font-weight: 700;
  font-size: 18px;
}

.logo-icon {
  font-size: 24px;
}

.logo-text {
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* --- Center Nav --- */
.desktop-nav {
  display: flex;
  gap: 4px;
}

.nav-item {
  position: relative;
}

.nav-link {
  display: block;
  padding: 8px 16px;
  color: var(--text-regular);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
  font-size: 14px;
}

.nav-link:hover {
  color: var(--color-primary);
  transform: translateY(-2px);
}

.nav-item.active .nav-link {
  color: var(--color-primary);
  font-weight: 600;
}

.nav-item.active::after {
  content: '';
  position: absolute;
  bottom: -4px;
  left: 50%;
  transform: translateX(-50%);
  width: 20px;
  height: 2px;
  background: var(--color-primary);
  border-radius: 1px;
}

/* --- Dropdown --- */
.nav-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  min-width: 140px;
  padding: 8px 0;
  opacity: 0;
  visibility: hidden;
  transform: translateY(-8px);
  transition: all var(--transition-fast);
  z-index: 1001;
}

.nav-item:hover .nav-dropdown {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

.dropdown-item {
  display: block;
  padding: 8px 20px;
  color: var(--text-regular);
  font-size: 13px;
  transition: all var(--transition-fast);
}

.dropdown-item:hover {
  color: var(--color-primary);
  background: rgba(64, 158, 255, 0.05);
}

/* --- Right --- */
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.user-avatar-area {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.user-avatar-area:hover {
  background: rgba(64, 158, 255, 0.05);
}

.username {
  font-size: 13px;
  color: var(--text-regular);
}

.arrow-icon {
  font-size: 12px;
  color: var(--text-secondary);
}

.notification-badge {
  cursor: pointer;
}

.hamburger-btn {
  display: none;
}

/* --- Mobile --- */
.mobile-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px;
}

.mobile-nav-item {
  padding: 12px 16px;
  color: var(--text-regular);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-size: 16px;
}

.mobile-nav-item:hover,
.mobile-nav-item.active {
  color: var(--color-primary);
  background: rgba(64, 158, 255, 0.05);
}

@media (max-width: 768px) {
  .desktop-nav {
    display: none;
  }

  .hamburger-btn {
    display: inline-flex;
  }

  .username {
    display: none;
  }
}
</style>
