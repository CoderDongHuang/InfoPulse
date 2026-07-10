<script setup lang="ts">
/**
 * InfoPulse — Global Layout
 * ==========================
 * Header + main content area (with route transitions) + Footer.
 */
import AppHeader from './AppHeader.vue'
import AppFooter from './AppFooter.vue'
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <div class="app-layout">
    <!-- Hide header on auth page for immersion -->
    <AppHeader v-if="route.path !== '/auth'" />

    <main class="main-content">
      <router-view v-slot="{ Component, route: r }">
        <transition :name="r.meta.transition as string || 'fade'" mode="out-in">
          <component :is="Component" :key="r.path" />
        </transition>
      </router-view>
    </main>

    <AppFooter v-if="route.path !== '/auth'" />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  min-height: calc(100vh - 120px);
}
</style>
