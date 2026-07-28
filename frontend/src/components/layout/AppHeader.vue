<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useWatchlistStore } from '@/stores/watchlist'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const watchlist = useWatchlistStore()
const mobileOpen = ref(false)

const navGroups = [
  { label: '开始工作', items: [
    { path: '/', label: 'Workspace', icon: 'House' },
    { path: '/hot-search', label: '数据看板', icon: 'TrendCharts' },
  ] },
  { label: '兼容工具', items: [
    { path: '/insight', label: '热点洞察', icon: 'DataAnalysis' },
    { path: '/timeline', label: '事件脉络', icon: 'Clock' },
    { path: '/mouthpiece', label: '表达工具', icon: 'EditPen' },
  ] },
  { label: '情报研究', items: [
    { path: '/search', label: '搜索中心', icon: 'Search' },
    { path: '/events', label: '事件中心', icon: 'Collection' },
  ] },
  { label: '个人空间', items: [
    { path: '/watchlist', label: '关注话题', icon: 'CollectionTag' },
    { path: '/history', label: '历史报告', icon: 'Files' },
  ] },
  { label: '平台管理', items: [
    { path: '/sources', label: '数据源中心', icon: 'Connection' },
  ] },
]
const navItems = navGroups.flatMap(group => group.items)

const active = (path: string) => route.path === path || (path === '/insight' && route.path === '/anti-scam') || (path === '/events' && route.path.startsWith('/events/'))

function navigate(path: string) {
  mobileOpen.value = false
  void router.push(path)
}

function handleUserCommand(command: string) {
  if (command === 'history') void router.push('/history')
  if (command === 'logout') { userStore.logout(); void router.push('/auth') }
}
</script>

<template>
  <aside class="topbar">
    <button class="brand" type="button" @click="navigate('/')">
      <span class="brand-mark"><span></span><span></span><span></span></span>
      <span><strong>InfoPulse</strong><small>AI Intelligence</small></span>
    </button>

    <nav class="desktop-nav" aria-label="主导航">
      <section v-for="group in navGroups" :key="group.label">
        <p>{{ group.label }}</p>
        <button v-for="item in group.items" :key="item.path" type="button" :title="item.label" :class="{ active: active(item.path) }" @click="navigate(item.path)">
          <el-icon><component :is="item.icon" /></el-icon>{{ item.label }}
        </button>
      </section>
    </nav>

    <div class="account-area">
      <button class="watch-count" type="button" title="关注话题" @click="navigate('/watchlist')"><el-icon><CollectionTag /></el-icon><span>{{ watchlist.count }}</span></button>
      <template v-if="userStore.isLoggedIn">
        <el-dropdown trigger="click" @command="handleUserCommand">
          <button class="profile-button" type="button">
            <span class="avatar">{{ userStore.userInfo?.username?.slice(0, 1).toUpperCase() || 'U' }}</span>
            <span class="profile-copy"><strong>{{ userStore.userInfo?.username }}</strong><small>个人工作区</small></span>
            <el-icon><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="history"><el-icon><Clock /></el-icon>历史报告</el-dropdown-item>
              <el-dropdown-item command="logout" divided><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
      <button v-else class="login-button" type="button" @click="navigate('/auth')">登录</button>
      <button class="menu-button" type="button" aria-label="打开导航" @click="mobileOpen = !mobileOpen"><el-icon><Menu /></el-icon></button>
    </div>
  </aside>

  <el-drawer v-model="mobileOpen" direction="rtl" size="82%" :with-header="false">
    <div class="mobile-panel">
      <div class="mobile-heading">InfoPulse</div>
      <button v-for="item in navItems" :key="item.path" type="button" :class="{ active: active(item.path) }" @click="navigate(item.path)">
        <el-icon><component :is="item.icon" /></el-icon>{{ item.label }}
      </button>
    </div>
  </el-drawer>
</template>

<style scoped>
.topbar { position: fixed; inset: 0 auto 0 0; z-index: 100; width: 220px; padding: 16px 14px 14px; display: flex; flex-direction: column; background: #fff; border-right: 1px solid var(--border-color); }
.brand, .desktop-nav button, .profile-button, .login-button, .menu-button, .mobile-panel button { border: 0; background: transparent; color: inherit; cursor: pointer; }
.brand { display: flex; align-items: center; gap: 11px; text-align: left; padding: 0; }
.brand > span:last-child { display: flex; flex-direction: column; line-height: 1.12; }
.brand strong { font-size: 18px; letter-spacing: .01em; }
.brand small, .profile-copy small { color: var(--text-secondary); font-size: 10px; margin-top: 3px; }
.brand-mark { width: 32px; height: 32px; display: flex; align-items: flex-end; gap: 3px; padding: 6px; background: #172033; border-radius: 6px; }
.brand-mark span { width: 4px; background: #fff; animation: pulsebar 1.6s ease-in-out infinite; }
.brand-mark span:nth-child(1) { height: 8px; }
.brand-mark span:nth-child(2) { height: 18px; animation-delay: .2s; background: #60a5fa; }
.brand-mark span:nth-child(3) { height: 12px; animation-delay: .4s; background: #ef746c; }
@keyframes pulsebar { 50% { transform: scaleY(.55); opacity: .65; } }
.desktop-nav { margin-top: 28px; display: grid; gap: 20px; }
.desktop-nav section { display: grid; gap: 4px; }.desktop-nav section > p { margin: 0 0 4px; padding: 0 10px; color: var(--text-secondary); font-size: 10px; font-weight: 700; }
.desktop-nav button { position: relative; min-height: 43px; padding: 0 12px; border-radius: 5px; display: inline-flex; gap: 10px; align-items: center; color: var(--text-regular); font-size: 12px; transition: color 160ms ease, background 160ms ease, transform 160ms ease; }
.desktop-nav button::after { content: ''; position: absolute; left: -16px; top: 8px; bottom: 8px; width: 3px; background: var(--brand-blue); transform: scaleY(0); transition: transform 180ms ease; }
.desktop-nav button:hover, .desktop-nav button.active { color: #1d4ed8; background: #eff5ff; }
.desktop-nav button.active::after { transform: scaleY(1); }
.account-area { margin-top: auto; padding-top: 16px; border-top: 1px solid #dce4e1; display: flex; align-items: center; gap: 8px; }
.watch-count { position: relative; width: 36px; height: 36px; flex: 0 0 auto; border: 1px solid #d4ded9; border-radius: 5px; display: grid; place-items: center; color: #557068; background: white; cursor: pointer; }.watch-count span { position: absolute; right: -4px; top: -5px; min-width: 16px; height: 16px; padding: 0 3px; border-radius: 8px; display: grid; place-items: center; color: white; background: #d95751; font-size: 9px; }
.profile-button { display: flex; align-items: center; gap: 8px; padding: 5px 7px; border-radius: 6px; }
.profile-button:hover { background: var(--surface-soft); }
.avatar { width: 34px; height: 34px; border-radius: 6px; display: grid; place-items: center; background: #d9eee9; color: #176f67; font-weight: 800; }
.profile-copy { display: flex; flex-direction: column; text-align: left; line-height: 1.05; }
.profile-copy strong { font-size: 12px; }
.login-button { min-height: 38px; padding: 0 18px; border-radius: 5px; color: white; background: #17241f; transition: transform 160ms ease, background 160ms ease; }.login-button:hover { transform: translateY(-1px); background: #167f76; }
.menu-button { display: none; font-size: 20px; }
.mobile-panel { padding: 28px 12px; display: grid; gap: 6px; }
.mobile-heading { padding: 0 12px 20px; font-size: 22px; font-weight: 900; }
.mobile-panel button { padding: 14px; display: flex; align-items: center; gap: 10px; border-radius: 6px; text-align: left; }
.mobile-panel button.active { background: #eaf3ff; color: #1267d6; }
@media (max-width: 980px) { .topbar { width: 72px; padding: 14px; align-items: center; }.brand > span:last-child { display: none; }.desktop-nav { margin-top: 28px; gap: 10px; }.desktop-nav section > p { display: none; }.desktop-nav button { width: 44px; padding: 0; justify-content: center; font-size: 0; }.desktop-nav button::after { left: -14px; }.desktop-nav button .el-icon { font-size: 17px; }.profile-copy, .profile-button > .el-icon, .watch-count { display: none; } }
@media (max-width: 720px) { .topbar { inset: 0 0 auto 0; width: auto; height: 64px; padding: 0 14px; flex-direction: row; justify-content: space-between; border-right: 0; border-bottom: 1px solid #d4ddda; }.brand > span:last-child { display: flex; }.desktop-nav { display: none; }.account-area { margin: 0; padding: 0; border: 0; }.watch-count { display: grid; }.menu-button { display: inline-grid; place-items: center; } }
</style>
