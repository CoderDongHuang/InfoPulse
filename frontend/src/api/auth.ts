/**
 * InfoPulse — Auth API
 * =====================
 * Typed API calls for authentication endpoints.
 */

import request from './request'

// --- Types ---
export interface UserResponse {
  id: string
  username: string
  email: string
  avatar_url: string
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

// --- API Calls ---
export const authApi = {
  async register(data: RegisterRequest): Promise<TokenResponse> {
    const res = await request.post('/auth/register', data)
    return res.data
  },

  async login(data: LoginRequest): Promise<TokenResponse> {
    const res = await request.post('/auth/login', data)
    return res.data
  },

  async refresh(): Promise<TokenResponse> {
    const res = await request.post('/auth/refresh')
    return res.data
  },

  async getMe(): Promise<UserResponse> {
    const res = await request.get('/auth/me')
    return res.data
  },

  async updateMe(data: Partial<RegisterRequest>): Promise<UserResponse> {
    const res = await request.put('/auth/me', data)
    return res.data
  },
}
