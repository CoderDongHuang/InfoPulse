/**
 * InfoPulse — Vue Router Configuration
 * =====================================
 * Route definitions + navigation guard for auth.
 */

import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '首页' },
  },
  {
    path: '/auth',
    name: 'Auth',
    component: () => import('@/views/AuthView.vue'),
    meta: { title: '登录', guest: true },
  },
  {
    path: '/anti-scam',
    name: 'AntiScam',
    component: () => import('@/views/anti-scam/AntiScamView.vue'),
    meta: { title: '避坑雷达', requiresAuth: true },
  },
  {
    path: '/mouthpiece',
    name: 'Mouthpiece',
    component: () => import('@/views/mouthpiece/MouthpieceView.vue'),
    meta: { title: '嘴替生成', requiresAuth: true },
  },
  {
    path: '/timeline',
    name: 'Timeline',
    component: () => import('@/views/timeline/TimelineView.vue'),
    meta: { title: '吃瓜时间线', requiresAuth: true },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// --- Navigation Guard ---
router.beforeEach((to, _from, next) => {
  // Update document title
  document.title = `${to.meta.title || 'InfoPulse'} — InfoPulse`

  const userStore = useUserStore()

  // If route requires auth and user is not logged in
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next({ path: '/auth', query: { redirect: to.fullPath } })
    return
  }

  // If user is already logged in and visits auth page
  if (to.meta.guest && userStore.isLoggedIn) {
    next({ path: '/' })
    return
  }

  next()
})

export default router
