import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

import { mockFetch, student } from './fetch-mock'

const TOKEN_KEY = 'zongce.token'

beforeEach(() => {
  sessionStorage.clear()
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('auth store', () => {
  it('登录：保存令牌与用户，判断角色', async () => {
    const { fetch, calls } = mockFetch({
      'POST /api/v1/auth/login': {
        status: 200,
        body: {
          access_token: 't1',
          token_type: 'bearer',
          must_change_password: false,
          user: student,
        },
      },
    })
    vi.stubGlobal('fetch', fetch)
    const auth = useAuthStore()
    await auth.login('TEST0002', 'Passw0rd!')
    expect(calls[0]?.body).toEqual({ username: 'TEST0002', password: 'Passw0rd!' })
    expect(auth.isAuthenticated).toBe(true)
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe('t1')
    expect(auth.hasRole('student')).toBe(true)
    expect(auth.hasRole('college_admin', 'class_reviewer')).toBe(false)
    auth.logout()
    expect([auth.isAuthenticated, sessionStorage.getItem(TOKEN_KEY)]).toEqual([false, null])
    expect(auth.roles).toEqual([])
  })

  it('登录失败抛出 ApiError，不保存令牌', async () => {
    const { fetch } = mockFetch({
      'POST /api/v1/auth/login': {
        status: 401,
        body: { error: { code: 'unauthorized', message: '账号或密码错误', details: null } },
      },
    })
    vi.stubGlobal('fetch', fetch)
    const auth = useAuthStore()
    await expect(auth.login('x', 'y')).rejects.toThrowError(ApiError)
    expect(auth.token).toBeNull()
  })

  it('刷新页面后用已保存的令牌恢复；失效时清除', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'saved')
    const { fetch, calls } = mockFetch({
      'GET /api/v1/auth/me': [
        { status: 200, body: { ...student, must_change_password: true } },
        {
          status: 401,
          body: { error: { code: 'unauthorized', message: '登录已失效', details: null } },
        },
      ],
    })
    vi.stubGlobal('fetch', fetch)
    const auth = useAuthStore()
    expect(await auth.restore()).toBe(true)
    expect(calls[0]?.authorization).toBe('Bearer saved')
    expect(auth.mustChangePassword).toBe(true)
    expect(await auth.restore()).toBe(true) // 已有用户信息，不再请求
    expect(calls).toHaveLength(1)

    setActivePinia(createPinia())
    const fresh = useAuthStore()
    expect(await fresh.restore()).toBe(false)
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(await fresh.restore()).toBe(false) // 没有令牌
  })

  it('修改密码后清除登录态（后端已使旧令牌失效）', async () => {
    const { fetch, calls } = mockFetch({
      'POST /api/v1/auth/login': {
        status: 200,
        body: {
          access_token: 't1',
          token_type: 'bearer',
          must_change_password: true,
          user: student,
        },
      },
      'POST /api/v1/auth/change-password': {
        status: 200,
        body: { message: '密码已修改，请重新登录' },
      },
    })
    vi.stubGlobal('fetch', fetch)
    const auth = useAuthStore()
    await auth.login('TEST0002', 'Init1234')
    await auth.changePassword('Init1234', 'NewPassw0rd')
    expect(calls[1]?.body).toEqual({ old_password: 'Init1234', new_password: 'NewPassw0rd' })
    expect(auth.isAuthenticated).toBe(false)
  })

  it('浏览器存储不可用时仍可在内存中登录', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('denied')
    })
    const { fetch } = mockFetch({
      'POST /api/v1/auth/login': {
        status: 200,
        body: {
          access_token: 't1',
          token_type: 'bearer',
          must_change_password: false,
          user: student,
        },
      },
    })
    vi.stubGlobal('fetch', fetch)
    const auth = useAuthStore()
    expect(auth.token).toBeNull()
    await auth.login('TEST0002', 'Passw0rd!')
    expect(auth.token).toBe('t1')
  })
})
