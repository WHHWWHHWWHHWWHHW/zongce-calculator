import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/auth'
import { useYearStore } from '@/stores/year'
import { loadRuleNames } from '@/utils/rules'

import { mockFetch } from './fetch-mock'

const YEARS = [
  { id: 3, name: '2026-2027', rule_version_id: 1, status: 'draft', created_at: '' },
  { id: 2, name: '2025-2026', rule_version_id: 1, status: 'open', created_at: '' },
  { id: 1, name: '2024-2025', rule_version_id: 1, status: 'closed', created_at: '' },
]

beforeEach(() => {
  sessionStorage.clear()
  setActivePinia(createPinia())
})
afterEach(() => vi.unstubAllGlobals())

describe('year store', () => {
  it('默认选中第一个未结束的学年，并记住选择', async () => {
    vi.stubGlobal('fetch', mockFetch({ 'GET /api/v1/years': { status: 200, body: YEARS } }).fetch)
    const store = useYearStore()
    await store.load()
    expect(store.selectedId).toBe(3)
    store.select(1)
    expect(store.selected?.name).toBe('2024-2025')
    expect(sessionStorage.getItem('zongce.year')).toBe('1')

    setActivePinia(createPinia())
    vi.stubGlobal('fetch', mockFetch({ 'GET /api/v1/years': { status: 200, body: YEARS } }).fetch)
    const again = useYearStore()
    await again.load()
    expect(again.selectedId).toBe(1)
    again.select(null)
    expect(sessionStorage.getItem('zongce.year')).toBeNull()
    expect(again.selected).toBeNull()
  })

  it('没有学年时为空；存储不可用时不报错', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('denied')
    })
    vi.stubGlobal('fetch', mockFetch({ 'GET /api/v1/years': { status: 200, body: [] } }).fetch)
    const store = useYearStore()
    await store.load()
    expect(store.selectedId).toBeNull()
    store.select(5)
    expect(store.selectedId).toBe(5)
    vi.restoreAllMocks()
  })
})

describe('loadRuleNames', () => {
  it('按版本缓存', async () => {
    const { fetch, calls } = mockFetch({
      'GET /api/v1/rules/7/content': {
        status: 200,
        body: { rules: { final: { id: 'final', name: '综合测评成绩' } }, ability_catalog: null },
      },
    })
    vi.stubGlobal('fetch', fetch)
    useAuthStore()
    expect(await loadRuleNames(7)).toEqual({ final: '综合测评成绩' })
    expect(await loadRuleNames(7)).toEqual({ final: '综合测评成绩' })
    expect(calls).toHaveLength(1)
  })
})
