/**
 * InfoPulse — User Store (Pinia)
 * ===============================
 * Manages authentication state: login, register, logout, token refresh.
 * NOTE: Access token is stored in Pinia memory only (not localStorage)
 * to prevent XSS attacks.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { UserResponse } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  // --- State ---
  const token = ref<string | null>(null)
  const userInfo = ref<UserResponse | null>(null)

  // --- Getters ---
  const isLoggedIn = computed(() => !!token.value)

  // --- Actions ---
  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password })
    token.value = res.access_token
    await fetchUserInfo()
  }

  async function register(username: string, email: string, password: string) {
    const res = await authApi.register({ username, email, password })
    token.value = res.access_token
    await fetchUserInfo()
  }

  async function fetchUserInfo() {
    if (!token.value) return
    userInfo.value = await authApi.getMe()
  }

  async function refreshToken() {
    try {
      const res = await authApi.refresh()
      token.value = res.access_token
      return true
    } catch {
      logout()
      return false
    }
  }

  function logout() {
    token.value = null
    userInfo.value = null
  }

  // Try to restore session on app load
  async function tryRestoreSession() {
    // No token in memory — nothing to restore
    // (Token is not persisted to localStorage for security)
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    login,
    register,
    logout,
    refreshToken,
    fetchUserInfo,
    tryRestoreSession,
  }
})
