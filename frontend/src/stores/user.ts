/**
 * InfoPulse — User Store (Pinia)
 * ===============================
 * Manages authentication state: login, register, logout, token refresh.
 * Tokens are scoped to the current browser tab via sessionStorage.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { UserResponse } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  let refreshInFlight: Promise<boolean> | null = null
  // --- State ---
  const token = ref<string | null>(sessionStorage.getItem('infopulse_access_token'))
  const refreshTokenValue = ref<string | null>(sessionStorage.getItem('infopulse_refresh_token'))
  const userInfo = ref<UserResponse | null>(null)

  // --- Getters ---
  const isLoggedIn = computed(() => !!token.value)

  // --- Actions ---
  async function login(username: string, password: string) {
    const res = await authApi.login({ username: username.trim(), password })
    persistTokens(res)
    await fetchUserInfo()
  }

  async function register(username: string, email: string, password: string) {
    const res = await authApi.register({ username: username.trim(), email: email.trim().toLowerCase(), password })
    persistTokens(res)
    await fetchUserInfo()
  }

  async function fetchUserInfo() {
    if (!token.value) return
    userInfo.value = await authApi.getMe()
  }

  async function refreshToken() {
    if (refreshInFlight) return refreshInFlight
    refreshInFlight = (async () => {
      try {
        if (!refreshTokenValue.value) return false
        const res = await authApi.refresh(refreshTokenValue.value)
        persistTokens(res)
        return true
      } catch {
        logout()
        return false
      }
    })()
    try { return await refreshInFlight }
    finally { refreshInFlight = null }
  }

  function logout() {
    token.value = null
    refreshTokenValue.value = null
    userInfo.value = null
    sessionStorage.removeItem('infopulse_access_token')
    sessionStorage.removeItem('infopulse_refresh_token')
  }

  // Try to restore session on app load
  async function tryRestoreSession() {
    if (!token.value) return
    try {
      await fetchUserInfo()
    } catch {
      const refreshed = await refreshToken()
      if (refreshed) {
        try { await fetchUserInfo() }
        catch { logout() }
      }
    }
  }

  function persistTokens(res: { access_token: string; refresh_token: string }) {
    token.value = res.access_token
    refreshTokenValue.value = res.refresh_token
    sessionStorage.setItem('infopulse_access_token', res.access_token)
    sessionStorage.setItem('infopulse_refresh_token', res.refresh_token)
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
