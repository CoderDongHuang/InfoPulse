<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import type { DropdownInstance } from 'element-plus'
import UserAvatar from './UserAvatar.vue'
import { primaryNavigation, visibleGroups, isActivePath } from './navigation'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const mobileOpen = ref(false)
const loggingOut = ref(false)
const navigationDropdowns = new Map<string, DropdownInstance>()
const accountDropdown = ref<DropdownInstance>()
function registerDropdown(label: string, instance: unknown) {
  if (instance) navigationDropdowns.set(label, instance as DropdownInstance)
  else navigationDropdowns.delete(label)
}
function closeDropdown(label: string, triggerId: string) {
  if (label === 'account') accountDropdown.value?.handleClose()
  else navigationDropdowns.get(label)?.handleClose()
  document.getElementById(triggerId)?.focus()
}
const groups = computed(() => visibleGroups(!!userStore.userInfo?.is_admin))
const mobileGroups = computed(() => [{ label: '开始工作', items: primaryNavigation }, ...groups.value])
const active = (path: string) => isActivePath(route.path, path)
watch(() => route.fullPath, () => { mobileOpen.value = false })

function navigate(path: string) {
  mobileOpen.value = false
  void router.push(path)
}
async function handleUserCommand(command: string) {
  if (command === 'profile') navigate('/profile')
  if (command === 'settings') navigate('/settings')
  if (command === 'logout' && !loggingOut.value) {
    loggingOut.value = true
    try { await userStore.logout(); await router.replace('/auth') }
    finally { loggingOut.value = false }
  }
}
</script>

<template>
  <a class="skip-link" href="#main-content">跳到主内容</a>
  <header class="topbar">
    <div class="header-inner">
      <router-link to="/" class="brand" aria-label="InfoPulse 工作台">
        <img class="brand-mark" src="/favicon.svg?v=pulse-1" alt="" width="34" height="34" />
        <strong>InfoPulse<span>情报工作空间</span></strong>
      </router-link>
      <nav class="desktop-nav" aria-label="主导航">
        <router-link v-for="item in primaryNavigation" :key="item.path" :to="item.path" :class="{ active: active(item.path) }" :aria-current="active(item.path) ? 'page' : undefined">{{ item.label }}</router-link>
        <el-dropdown v-for="(group, index) in groups" :key="group.label" :ref="(instance: unknown) => registerDropdown(group.label, instance)" trigger="click" placement="bottom" @command="navigate" :max-height="640" popper-class="navigation-popper">
          <button :id="`nav-trigger-${index}`" type="button" class="nav-trigger" :class="{ active: group.items.some(item => active(item.path)) }" @keydown.esc.stop.prevent="closeDropdown(group.label, `nav-trigger-${index}`)">{{ group.label }}<el-icon><ArrowDown /></el-icon></button>
          <template #dropdown><el-dropdown-menu class="mega-menu" :style="{ '--nav-columns': group.sections.length }" @keydown.esc.stop.prevent="closeDropdown(group.label, `nav-trigger-${index}`)">
            <li v-for="section in group.sections" :key="section.label" class="nav-category" role="none">
              <h2>{{ section.label }}</h2><p>{{ section.description }}</p>
              <ul role="group" :aria-label="section.label">
                <el-dropdown-item v-for="item in section.items" :key="item.path" :command="item.path" :class="{ 'current-menu-item': active(item.path) }"><el-icon><component :is="item.icon" /></el-icon>{{ item.label }}</el-dropdown-item>
              </ul>
            </li>
          </el-dropdown-menu></template>
        </el-dropdown>
      </nav>
      <div class="account-area">
        <el-dropdown v-if="userStore.isLoggedIn" ref="accountDropdown" trigger="click" @command="handleUserCommand">
          <button id="account-trigger" class="profile-button" type="button" aria-label="账户菜单" :disabled="loggingOut" :aria-busy="loggingOut" @keydown.esc.stop.prevent="closeDropdown('account', 'account-trigger')">
            <UserAvatar :username="userStore.userInfo?.username" :url="userStore.userInfo?.avatar_url" />
            <el-icon><ArrowDown /></el-icon>
          </button>
          <template #dropdown><el-dropdown-menu @keydown.esc.stop.prevent="closeDropdown('account', 'account-trigger')">
            <el-dropdown-item command="profile"><el-icon aria-hidden="true"><User /></el-icon>个人中心</el-dropdown-item>
            <el-dropdown-item command="settings"><el-icon aria-hidden="true"><Setting /></el-icon>私人配置</el-dropdown-item>
            <el-dropdown-item command="logout" divided :disabled="loggingOut"><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
        <router-link v-else class="login-button" to="/auth">登录</router-link>
        <button class="menu-button" type="button" aria-label="打开导航" :aria-expanded="mobileOpen" @click="mobileOpen = !mobileOpen"><el-icon><Menu /></el-icon></button>
      </div>
    </div>
  </header>
  <el-drawer v-model="mobileOpen" title="全部导航" direction="rtl" size="min(360px, 92vw)">
    <nav class="mobile-panel" aria-label="移动导航">
      <section v-for="group in mobileGroups" :key="group.label"><h2>{{ group.label }}</h2>
        <router-link v-for="item in group.items" :key="item.path" :to="item.path" :class="{ active: active(item.path) }" :aria-current="active(item.path) ? 'page' : undefined" @click="mobileOpen = false"><el-icon><component :is="item.icon" /></el-icon>{{ item.label }}</router-link>
      </section>
    </nav>
  </el-drawer>
</template>

<style scoped>
.skip-link { position: fixed; top: -60px; left: 16px; z-index: 3000; padding: 10px 16px; background: #fff; color: #1d4ed8; }
.skip-link:focus { top: 8px; }
.topbar { position: fixed; inset: 0 0 auto; z-index: 100; height: 68px; background: #fff; border-bottom: 1px solid var(--border-color); }
.header-inner { height: 100%; max-width: 1600px; margin: auto; padding: 0 32px; display: flex; align-items: center; gap: 36px; }
.brand { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.brand strong { font-size: 19px; letter-spacing: -.6px; line-height: 1.15; }
.brand strong span { display: block; margin-top: 4px; font-size: 10px; letter-spacing: 1px; color: var(--text-secondary); font-weight: 400; }
.brand-mark { width: 34px; height: 34px; display: block; flex-shrink: 0; }
.desktop-nav { display: flex; gap: 6px; align-items: center; }
.desktop-nav > a, .nav-trigger { min-height: 38px; padding: 0 12px; display: inline-flex; align-items: center; gap: 7px; border: 0; border-radius: 7px; color: #475569; background: transparent; cursor: pointer; font-size: 13px; white-space: nowrap; }
.desktop-nav a:hover, .nav-trigger:hover, .desktop-nav .active, .mobile-panel .active { background: #eff4ff; color: #1d4ed8; }
.nav-trigger .el-icon { font-size: 10px; }
.account-area { margin-left: auto; display: flex; align-items: center; gap: 18px; }
.preview-label { color: #64748b; font-size: 10px; border: 1px solid #e2e8f0; border-radius: 5px; padding: 3px 7px; white-space: nowrap; }
.profile-button, .menu-button { display: flex; align-items: center; gap: 8px; padding: 4px; border: 0; border-radius: 8px; background: transparent; cursor: pointer; color: #64748b; }
.profile-button:hover { background: #f1f5f9; }.profile-button > .el-icon { font-size: 11px; }
.login-button { background: #2563eb; color: #fff; border-radius: 6px; padding: 7px 16px; }
.menu-button { display: none; font-size: 22px; min-width: 36px; min-height: 40px; justify-content: center; }
.mobile-panel section { margin-bottom: 24px; }.mobile-panel h2 { font-size: 11px; color: #64748b; margin: 0 0 8px; }
.mobile-panel a { display: flex; align-items: center; gap: 12px; padding: 11px 12px; border-radius: 7px; font-size: 14px; }
@media (max-width: 1180px) { .header-inner { gap: 20px; padding: 0 24px; }.preview-label { display: none; } }
@media (max-width: 1050px) { .desktop-nav { display: none; }.menu-button { display: flex; } }
@media (max-width: 600px) { .header-inner { padding: 0 16px; }.account-area { gap: 12px; }.brand strong { font-size: 17px; } }
</style>
<style>
.current-menu-item { color: #1d4ed8 !important; background: #eff4ff; }
.navigation-popper { max-width: calc(100vw - 32px); }
.navigation-popper .mega-menu { display: grid; grid-template-columns: repeat(var(--nav-columns), minmax(170px, 1fr)); gap: 12px; padding: 22px; width: min(880px, calc(100vw - 48px)); box-sizing: border-box; }
.nav-category { list-style: none; min-width: 0; padding: 0 10px; border-left: 1px solid #eef2f6; }
.nav-category:first-child { border-left: 0; }
.nav-category h2 { margin: 0 8px 7px; color: #0f172a; font-size: 14px; font-weight: 650; }
.nav-category p { margin: 0 8px 16px; color: #64748b; font-size: 11px; }
.nav-category ul { margin: 0; padding: 0; }
.nav-category .el-dropdown-menu__item { min-height: 40px; padding: 8px; border-radius: 6px; white-space: normal; line-height: 1.5; }
</style>
