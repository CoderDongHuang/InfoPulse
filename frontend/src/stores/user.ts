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
  let refreshEpoch = -1
  let sessionEpoch = 0
  // --- State ---
  const token = ref<string | null>(sessionStorage.getItem('infopulse_access_token'))
  const refreshTokenValue = ref<string | null>(sessionStorage.getItem('infopulse_refresh_token'))
  const userInfo = ref<UserResponse | null>(null)

  // --- Getters ---
  const isLoggedIn = computed(() => !!token.value)

  // --- Actions ---
  async function login(username: string, password: string) {
    const epoch = ++sessionEpoch
    const res = await authApi.login({ username: username.trim(), password })
    if (epoch !== sessionEpoch) return
    persistTokens(res)
    await fetchUserInfo()
  }

  async function register(username: string, email: string, password: string) {
    const epoch = ++sessionEpoch
    const res = await authApi.register({ username: username.trim(), email: email.trim().toLowerCase(), password })
    if (epoch !== sessionEpoch) return
    persistTokens(res)
    await fetchUserInfo()
  }

  async function fetchUserInfo() {
    if (!token.value) return
    const epoch = sessionEpoch
    const info = await authApi.getMe()
    if (epoch === sessionEpoch) userInfo.value = info
  }

  async function refreshToken() {
    if (refreshInFlight && refreshEpoch === sessionEpoch) return refreshInFlight
    refreshEpoch = sessionEpoch
    refreshInFlight = (async () => {
      const epoch = sessionEpoch
      try {
        if (!refreshTokenValue.value) return false
        const res = await authApi.refresh(refreshTokenValue.value)
        if (epoch !== sessionEpoch) return false
        persistTokens(res)
        return true
      } catch {
        if (epoch === sessionEpoch) void logout()
        return false
      }
    })()
    const current = refreshInFlight
    try { return await current }
    finally { if (refreshInFlight === current) refreshInFlight = null }
  }

  async function logout() {
    const previousToken = token.value
    sessionEpoch += 1
    token.value = null
    refreshTokenValue.value = null
    userInfo.value = null
    sessionStorage.removeItem('infopulse_access_token')
    sessionStorage.removeItem('infopulse_refresh_token')
    if (previousToken) {
      try { await authApi.logout(previousToken) } catch { /* local session remains cleared */ }
    }
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
