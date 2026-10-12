import type { Pinia } from 'pinia'
import { createRouter, createWebHistory, type Router, type RouteRecordRaw } from 'vue-router'

import type { Role } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

import { decide } from './guard'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    roles?: Role[]
    title?: string
  }
}

// 页面待组件库选定后实现（CLAUDE.md §13 第 7 项）；目前只有登录、改密与占位页
export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/change-password',
    name: 'change-password',
    component: () => import('@/views/ChangePasswordView.vue'),
    meta: { title: '修改密码' },
  },
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '首页' },
  },
  {
    path: '/review',
    name: 'review',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { roles: ['class_reviewer', 'college_admin'], title: '审核工作台' },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { roles: ['college_admin'], title: '管理后台' },
  },
  {
    path: '/forbidden',
    name: 'forbidden',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { title: '没有权限' },
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export function setupRouter(pinia: Pinia): Router {
  const router = createRouter({ history: createWebHistory(), routes })
  router.beforeEach(async (to) => {
    const auth = useAuthStore(pinia)
    await auth.restore()
    return decide(to, {
      isAuthenticated: auth.isAuthenticated,
      mustChangePassword: auth.mustChangePassword,
      roles: auth.roles,
    })
  })
  return router
}
