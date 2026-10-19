import { ApiError } from '@/api/client'

/** 把异常转成给用户看的提示。 */
export function errorMessage(error: unknown, fallback = '操作失败，请稍后重试'): string {
  if (error instanceof ApiError) {
    if (error.code === 'validation_error' && Array.isArray(error.details)) {
      const first = error.details[0] as { msg?: unknown } | undefined
      if (first && typeof first.msg === 'string') return `${error.message}：${first.msg}`
    }
    return error.message
  }
  return fallback
}
