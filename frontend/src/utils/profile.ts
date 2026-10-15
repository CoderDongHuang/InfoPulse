import type { ProfileUpdateRequest } from '@/api/auth'

export interface ProfileFields { username: string; email: string; avatar_url: string }

// Never render javascript:, data:, credentials, or relative URLs from stored profiles.
export function safeAvatarUrl(value: string): string {
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : ''
  } catch { return '' }
}

export function profilePatch(form: ProfileFields, saved: ProfileFields): ProfileUpdateRequest {
  const patch: ProfileUpdateRequest = {}
  const username = form.username.trim()
  const email = form.email.trim().toLowerCase()
  const avatar = form.avatar_url.trim()
  if (username !== saved.username) {
    if (username.length < 3 || username.length > 50 || username.includes('@')) throw new Error('用户名需为 3–50 个字符，且不能包含 @。')
    patch.username = username
  }
  if (email !== saved.email) {
    if (!email || email.length > 100) throw new Error('请填写有效邮箱（不超过 100 个字符）。')
    patch.email = email
  }
  if (avatar !== saved.avatar_url) {
    if (avatar.length > 500 || (avatar && !safeAvatarUrl(avatar))) throw new Error('头像地址需为 HTTP/HTTPS 链接，不包含账号密码，最多 500 个字符；留空可恢复默认头像。')
    patch.avatar_url = avatar
  }
  return patch
}
