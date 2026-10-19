import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'

import { useNarrow } from '@/utils/viewport'

afterEach(() => vi.unstubAllGlobals())

describe('useNarrow', () => {
  it('跟随媒体查询变化，组件卸载时移除监听', async () => {
    let listener: ((e: MediaQueryListEvent) => void) | undefined
    const mql = {
      matches: true,
      addEventListener: vi.fn((_: string, fn: (e: MediaQueryListEvent) => void) => {
        listener = fn
      }),
      removeEventListener: vi.fn(),
    }
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => mql),
    )
    const wrapper = mount(
      defineComponent({
        setup() {
          const narrow = useNarrow()
          return () => h('span', narrow.value ? 'narrow' : 'wide')
        },
      }),
    )
    expect(wrapper.text()).toBe('narrow')
    listener?.({ matches: false } as MediaQueryListEvent)
    await nextTick()
    expect(wrapper.text()).toBe('wide')
    wrapper.unmount()
    expect(mql.removeEventListener).toHaveBeenCalledOnce()
  })

  it('不支持 matchMedia 时视为宽屏', () => {
    vi.stubGlobal('matchMedia', undefined)
    expect(useNarrow().value).toBe(false)
  })
})
