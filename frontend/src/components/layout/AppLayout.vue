<script setup lang="ts">
import AppHeader from './AppHeader.vue'
import AppFooter from './AppFooter.vue'
import TopToolbar from './TopToolbar.vue'
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <div class="app-layout" :class="`route-${String(route.name || 'page').toLowerCase()}`">
    <AppHeader v-if="route.path !== '/auth'" />
    <TopToolbar v-if="route.path !== '/auth'" />
    <main class="main-content">
      <router-view v-slot="{ Component, route: currentRoute }">
        <transition name="page" mode="out-in">
          <component :is="Component" :key="currentRoute.fullPath" />
        </transition>
      </router-view>
    </main>
    <AppFooter v-if="route.path !== '/auth'" />
  </div>
</template>

<style scoped>
.app-layout { min-height: 100vh; }
.main-content { min-height: 100vh; padding-top: 56px; padding-left: 220px; }
.route-auth .main-content { padding-left: 0; }
.route-auth .main-content { padding-top: 0; }
.app-layout :deep(.app-footer) { margin-left: 220px; }
.page-enter-active, .page-leave-active { transition: opacity 180ms ease, transform 180ms ease; }
.page-enter-from { opacity: 0; transform: translateY(8px); }
.page-leave-to { opacity: 0; transform: translateY(-4px); }
@media (max-width: 980px) { .main-content { padding-left: 72px; }.app-layout :deep(.app-footer) { margin-left: 72px; } }
@media (max-width: 720px) { .main-content { padding-left: 0; padding-top: 116px; }.app-layout :deep(.app-footer) { margin-left: 0; } }
</style>
