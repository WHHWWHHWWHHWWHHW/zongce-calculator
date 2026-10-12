import { createPinia, setActivePinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Role } from '@/api/client'
import { setupRouter } from '@/router'
import { decide, type GuardState } from '@/router/guard'

import { mockFetch, student } from './fetch-mock'

const loggedIn = (roles: Role[], mustChangePassword = false): GuardState => ({
  isAuthenticated: true,
  mustChangePassword,
  roles,
})
const anonymous: GuardState = { isAuthenticated: false, mustChangePassword: false, roles: [] }
const target = (
  name: string,
  fullPath: string,
  meta: { public?: boolean; roles?: Role[] } = {},
) => ({
  name,
  fullPath,
  meta,
})

describe('decide', () => {
  it('公开页面：未登录可访问，已登录访问登录页回首页', () => {
    expect(decide(target('login', '/login', { public: true }), anonymous)).toBe(true)
    expect(decide(target('login', '/login', { public: true }), loggedIn(['student']))).toEqual({
      name: 'home',
    })
  })

  it('未登录跳转登录页并记住目标地址', () => {
    expect(decide(target('admin', '/admin'), anonymous)).toEqual({
      name: 'login',
      query: { redirect: '/admin' },
    })
  })

  it('未修改初始密码只能进入改密页', () => {
    const state = loggedIn(['student'], true)
    expect(decide(target('home', '/'), state)).toEqual({ name: 'change-password' })
    expect(decide(target('change-password', '/change-password'), state)).toBe(true)
  })

  it('按角色限制页面', () => {
    const review = target('review', '/review', { roles: ['class_reviewer', 'college_admin'] })
    expect(decide(review, loggedIn(['student']))).toEqual({ name: 'forbidden' })
    expect(decide(review, loggedIn(['student', 'class_reviewer']))).toBe(true)
    expect(decide(target('home', '/'), loggedIn(['student']))).toBe(true)
  })
})

describe('setupRouter', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('守卫接入路由：未登录访问管理后台被带到登录页；登录后可进入首页', async () => {
    sessionStorage.clear()
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
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = setupRouter(pinia)
    await router.push('/admin')
    expect(router.currentRoute.value.fullPath).toBe('/login?redirect=/admin')

    const { useAuthStore } = await import('@/stores/auth')
    await useAuthStore(pinia).login('TEST0002', 'Passw0rd!')
    await router.push('/admin')
    expect(router.currentRoute.value.name).toBe('forbidden')
    await router.push('/nowhere')
    expect(router.currentRoute.value.name).toBe('home')
  })
})
