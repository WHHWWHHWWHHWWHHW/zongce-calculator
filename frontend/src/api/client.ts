/**
 * 类型化 API 客户端。类型由 docs/api/openapi.json 生成（pnpm gen:api），不手写。
 * 分数一律是十进制字符串，前端只展示、不计算（CLAUDE.md §6）。
 */
import createClient, { type Client, type Middleware } from 'openapi-fetch'

import type { components, paths } from './schema'

export type Schemas = components['schemas']
export type Role = Schemas['Role']
export type UserOut = Schemas['UserOut']

/** 后端统一错误结构：{"error": {"code", "message", "details"}} */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: unknown = null,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

interface ErrorBody {
  error?: { code?: unknown; message?: unknown; details?: unknown }
}

export function toApiError(status: number, body: unknown): ApiError {
  const error = (body as ErrorBody | null | undefined)?.error
  if (error && typeof error.code === 'string' && typeof error.message === 'string') {
    return new ApiError(status, error.code, error.message, error.details ?? null)
  }
  return new ApiError(status, `http_${status}`, `请求失败（HTTP ${status}）`)
}

/** 把 openapi-fetch 的结果转换为数据或抛出 ApiError。 */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    throw toApiError(result.response.status, result.error)
  }
  return result.data as T
}

export interface ClientOptions {
  baseUrl?: string
  getToken: () => string | null
  onUnauthorized?: () => void
  fetch?: typeof globalThis.fetch
}

export function createApiClient(options: ClientOptions): Client<paths> {
  const client = createClient<paths>({
    baseUrl: options.baseUrl ?? '',
    ...(options.fetch ? { fetch: options.fetch } : {}),
  })
  const auth: Middleware = {
    onRequest({ request }) {
      const token = options.getToken()
      if (token) request.headers.set('Authorization', `Bearer ${token}`)
      return request
    },
    onResponse({ response }) {
      if (response.status === 401) options.onUnauthorized?.()
      return response
    },
  }
  client.use(auth)
  return client
}
