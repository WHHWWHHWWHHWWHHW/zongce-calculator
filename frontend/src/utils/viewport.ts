/** 窄屏判断（手机宽度）：用于在窄屏上取消表格固定列等。 */
import { getCurrentInstance, onBeforeUnmount, type Ref, ref } from 'vue'

export function useNarrow(query = '(max-width: 600px)'): Ref<boolean> {
  const mql = typeof window.matchMedia === 'function' ? window.matchMedia(query) : null
  const narrow = ref(mql?.matches ?? false)
  if (mql) {
    const update = (event: MediaQueryListEvent) => {
      narrow.value = event.matches
    }
    mql.addEventListener('change', update)
    if (getCurrentInstance()) onBeforeUnmount(() => mql.removeEventListener('change', update))
  }
  return narrow
}
