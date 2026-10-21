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
    /** 是否显示在顶栏菜单 */
    menu?: boolean
  }
}

const STUDENT: Role[] = ['student']
const REVIEWER: Role[] = ['class_reviewer', 'college_admin']
const ADMIN: Role[] = ['college_admin']

export const appRoutes: RouteRecordRaw[] = [
  {
    path: '',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '首页', menu: true },
  },
  {
    path: 'my/declarations',
    name: 'my-declarations',
    component: () => import('@/views/MyDeclarationsView.vue'),
    meta: { title: '我的申报', roles: STUDENT, menu: true },
  },
  {
    path: 'my/scores',
    name: 'my-scores',
    component: () => import('@/views/MyScoresView.vue'),
    meta: { title: '我的成绩', roles: STUDENT, menu: true },
  },
  {
    path: 'preview',
    name: 'preview',
    component: () => import('@/views/ScorePreviewView.vue'),
    meta: { title: '成绩预估', menu: true },
  },
  {
    path: 'publications',
    name: 'publications',
    component: () => import('@/views/PublicationsView.vue'),
    meta: { title: '公示', menu: true },
  },
  {
    path: 'review',
    name: 'review',
    component: () => import('@/views/ReviewView.vue'),
    meta: { title: '审核工作台', roles: REVIEWER, menu: true },
  },
  {
    path: 'review/match',
    name: 'match',
    component: () => import('@/views/MatchView.vue'),
    meta: { title: '名单比对', roles: REVIEWER, menu: true },
  },
  {
    path: 'admin',
    name: 'admin',
    component: () => import('@/views/AdminView.vue'),
    meta: { title: '管理后台', roles: ADMIN, menu: true },
  },
  {
    path: 'change-password',
    name: 'change-password',
    component: () => import('@/views/ChangePasswordView.vue'),
    meta: { title: '修改密码' },
  },
  {
    path: 'forbidden',
    name: 'forbidden',
    component: () => import('@/views/ForbiddenView.vue'),
    meta: { title: '没有权限' },
  },
]

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  { path: '/', component: () => import('@/layouts/AppLayout.vue'), children: appRoutes },
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
  router.afterEach((to) => {
    document.title = to.meta.title ? `${to.meta.title} · 综测智能核算平台` : '综测智能核算平台'
  })
  return router
}
