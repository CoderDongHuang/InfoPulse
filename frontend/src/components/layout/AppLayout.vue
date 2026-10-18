<script setup lang="ts">
import AppHeader from './AppHeader.vue'
import AppFooter from './AppFooter.vue'
import TopToolbar from './TopToolbar.vue'
import EnvironmentNotice from './EnvironmentNotice.vue'
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <div class="app-layout" :class="`route-${String(route.name || 'page').toLowerCase()}`">
    <AppHeader v-if="route.path !== '/auth'" />
    <TopToolbar v-if="route.path !== '/auth'" />
    <main id="main-content" class="main-content" tabindex="-1">
      <EnvironmentNotice />
      <router-view v-slot="{ Component, route: currentRoute }">
        <transition name="page" mode="out-in">
          <component :is="Component" :key="currentRoute.path === '/agent' ? currentRoute.path : currentRoute.fullPath" />
        </transition>
      </router-view>
    </main>
    <AppFooter v-if="route.path !== '/auth'" />
  </div>
</template>

<style scoped>
.app-layout { min-height: 100vh; }
.main-content { min-height: calc(100vh - 44px); padding-top: 124px; }
.route-auth .main-content { padding-top: 0; }
.route-agent .main-content { height: 100dvh; min-height: 0; box-sizing: border-box; display: flex; flex-direction: column; }
.route-agent .main-content :deep(.environment-notice) { flex-shrink: 0; }
.route-agent .main-content :deep(.agent) { flex: 1; min-height: 0; height: auto; }
.page-enter-active, .page-leave-active { transition: opacity 180ms ease, transform 180ms ease; }
.page-enter-from { opacity: 0; transform: translateY(8px); }
.page-leave-to { opacity: 0; transform: translateY(-4px); }
@media (max-width: 720px) { .main-content { padding-top: 120px; }.route-auth .main-content { padding-top: 0; } }
</style>
