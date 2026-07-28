/**
 * InfoPulse — Axios Instance
 * ===========================
 * Pre-configured Axios with interceptors for auth, errors, loading.
 */

import axios, { type AxiosInstance, type AxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

export interface ApiErrorPayload {
  error?: { code?: string; message?: string; details?: unknown; diagnostic_id?: string }
  detail?: string
}

export function getApiError(error: AxiosError<ApiErrorPayload>) {
  const data = error.response?.data
  return {
    code: data?.error?.code || `HTTP_${error.response?.status || 0}`,
    message: data?.error?.message || data?.detail || error.message || '请求失败，请重试',
    diagnosticId: data?.error?.diagnostic_id || error.response?.headers?.['x-request-id'],
  }
}

const request: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// --- Request Interceptor ---
request.interceptors.request.use(
  (config) => {
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// --- Response Interceptor ---
request.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const userStore = useUserStore()

    if (!error.response) {
      // Network error
      if (!navigator.onLine) {
        ElMessage.error('网络连接异常，请检查网络后重试')
      } else {
        ElMessage.error('服务器连接超时，请稍后重试')
      }
      return Promise.reject(error)
    }

    const { status } = error.response

    switch (status) {
      case 401:
        if (error.config?.headers?.['X-Skip-Auth-Refresh'] || (error.config as any)?._retry) {
          userStore.logout()
          return Promise.reject(error)
        }
        if (error.config) (error.config as any)._retry = true
        // Try token refresh
        const refreshed = await userStore.refreshToken()
        if (refreshed && error.config) {
          // Retry the original request with new token
          error.config.headers.Authorization = `Bearer ${userStore.token}`
          return request(error.config)
        }
        // Refresh failed — redirect to login
        userStore.logout()
        window.location.href = '/auth'
        break

      case 403:
        ElMessage.error('权限不足')
        break

      case 500:
        ElMessage.error('服务器开小差了，请稍后重试')
        break

      default:
        if (error.config?.headers?.['X-Suppress-Error-Message']) break
        ElMessage.error(getApiError(error as AxiosError<ApiErrorPayload>).message)
    }

    return Promise.reject(error)
  }
)

export default request
