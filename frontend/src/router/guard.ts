/** 路由守卫的判定逻辑（纯函数，便于单元测试）。 */
import type { RouteLocationRaw } from 'vue-router'

import type { Role } from '@/api/client'

export interface GuardState {
  isAuthenticated: boolean
  mustChangePassword: boolean
  roles: Role[]
}

export interface GuardTarget {
  name?: string | symbol | null
  fullPath: string
  meta: { public?: boolean; roles?: Role[] }
}

export function decide(to: GuardTarget, state: GuardState): true | RouteLocationRaw {
  if (to.meta.public) {
    return state.isAuthenticated && to.name === 'login' ? { name: 'home' } : true
  }
  if (!state.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (state.mustChangePassword && to.name !== 'change-password') {
    return { name: 'change-password' }
  }
  const required = to.meta.roles
  if (required && !required.some((role) => state.roles.includes(role))) {
    return { name: 'forbidden' }
  }
  return true
}
