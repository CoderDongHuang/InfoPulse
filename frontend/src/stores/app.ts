/**
 * InfoPulse — App Store (Pinia)
 * ==============================
 * Global application state: theme, loading indicator, header title.
 */

import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useAppStore = defineStore('app', () => {
  // --- State ---
  const theme = ref<'light' | 'dark'>(
    (localStorage.getItem('theme') as 'light' | 'dark') || 'light'
  )
  const globalLoading = ref(false)
  const headerTitle = ref('')

  // --- Actions ---
  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
    localStorage.setItem('theme', theme.value)
  }

  function setLoading(loading: boolean) {
    globalLoading.value = loading
  }

  function setHeaderTitle(title: string) {
    headerTitle.value = title
  }

  // Apply theme to document
  watch(theme, (newTheme) => {
    document.documentElement.setAttribute('data-theme', newTheme)
  }, { immediate: true })

  return {
    theme,
    globalLoading,
    headerTitle,
    toggleTheme,
    setLoading,
    setHeaderTitle,
  }
})
