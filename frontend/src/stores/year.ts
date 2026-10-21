/** 当前选中的学年（各页面共用，记在 sessionStorage）。 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { type Schemas, unwrap } from '@/api/client'

import { useAuthStore } from './auth'

const KEY = 'zongce.year'

export const useYearStore = defineStore('year', () => {
  const years = ref<Schemas['YearOut'][]>([])
  const selectedId = ref<number | null>(null)
  const selected = computed(() => years.value.find((y) => y.id === selectedId.value) ?? null)

  function select(id: number | null): void {
    selectedId.value = id
    try {
      if (id === null) sessionStorage.removeItem(KEY)
      else sessionStorage.setItem(KEY, String(id))
    } catch {
      // 存储不可用时只记在内存
    }
  }

  async function load(): Promise<void> {
    const auth = useAuthStore()
    years.value = unwrap(await auth.api.GET('/api/v1/years'))
    let saved: number | null = null
    try {
      saved = Number(sessionStorage.getItem(KEY)) || null
    } catch {
      saved = null
    }
    const preferred =
      years.value.find((y) => y.id === saved) ??
      years.value.find((y) => y.status !== 'closed') ??
      years.value[0]
    select(preferred?.id ?? null)
  }

  return { years, selectedId, selected, select, load }
})
