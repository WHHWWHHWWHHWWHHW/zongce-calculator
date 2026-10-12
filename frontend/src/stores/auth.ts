/** 登录态：令牌存在 sessionStorage（关闭浏览器即失效），用户信息从后端获取。 */
import type { Client } from 'openapi-fetch'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { createApiClient, type Role, unwrap, type UserOut } from '@/api/client'
import type { paths } from '@/api/schema'

const TOKEN_KEY = 'zongce.token'

function readToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function writeToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // 隐私模式等情况下存储不可用：只保留在内存中
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(readToken())
  const user = ref<UserOut | null>(null)

  const api: Client<paths> = createApiClient({
    baseUrl: import.meta.env.VITE_API_BASE ?? '',
    getToken: () => token.value,
    onUnauthorized: () => clear(),
  })

  const isAuthenticated = computed(() => token.value !== null && user.value !== null)
  const roles = computed<Role[]>(() => user.value?.roles ?? [])
  const mustChangePassword = computed(() => user.value?.must_change_password ?? false)

  function clear(): void {
    token.value = null
    user.value = null
    writeToken(null)
  }

  function hasRole(...wanted: Role[]): boolean {
    return wanted.some((role) => roles.value.includes(role))
  }

  async function login(username: string, password: string): Promise<UserOut> {
    const body = unwrap(await api.POST('/api/v1/auth/login', { body: { username, password } }))
    token.value = body.access_token
    user.value = body.user
    writeToken(body.access_token)
    return body.user
  }

  /** 页面刷新后用已保存的令牌恢复登录态；令牌失效时清除。 */
  async function restore(): Promise<boolean> {
    if (token.value === null) return false
    if (user.value !== null) return true
    try {
      user.value = unwrap(await api.GET('/api/v1/auth/me'))
      return true
    } catch {
      clear()
      return false
    }
  }

  /** 修改密码后后端会使旧令牌失效，需要重新登录。 */
  async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
    unwrap(
      await api.POST('/api/v1/auth/change-password', {
        body: { old_password: oldPassword, new_password: newPassword },
      }),
    )
    clear()
  }

  return {
    api,
    token,
    user,
    isAuthenticated,
    roles,
    mustChangePassword,
    hasRole,
    login,
    restore,
    changePassword,
    logout: clear,
  }
})
