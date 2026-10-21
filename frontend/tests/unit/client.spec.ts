import { describe, expect, it, vi } from 'vitest'

import { ApiError, createApiClient, toApiError, unwrap } from '@/api/client'

import { mockFetch } from './fetch-mock'

describe('toApiError', () => {
  it('解析后端统一错误结构', () => {
    const error = toApiError(403, {
      error: {
        code: 'password_change_required',
        message: '首次登录请先修改初始密码',
        details: null,
      },
    })
    expect(error).toBeInstanceOf(ApiError)
    expect([error.status, error.code, error.message]).toEqual([
      403,
      'password_change_required',
      '首次登录请先修改初始密码',
    ])
  })

  it('无法识别的响应体给出通用提示', () => {
    for (const body of [null, 'oops', { error: { code: 1 } }]) {
      const error = toApiError(502, body)
      expect([error.code, error.message]).toEqual(['http_502', '请求失败（HTTP 502）'])
    }
  })
})

describe('createApiClient', () => {
  it('自动带上令牌；成功时 unwrap 返回数据', async () => {
    const { fetch, calls } = mockFetch({
      'GET /api/v1/health': { status: 200, body: { status: 'ok', version: '0.1.0' } },
    })
    const client = createApiClient({ baseUrl: 'http://api.test', getToken: () => 'abc', fetch })
    const data = unwrap(await client.GET('/api/v1/health'))
    expect(data).toEqual({ status: 'ok', version: '0.1.0' })
    expect(calls[0]?.authorization).toBe('Bearer abc')
  })

  it('没有令牌时不带 Authorization；401 时通知登出', async () => {
    const onUnauthorized = vi.fn()
    const { fetch, calls } = mockFetch({
      'GET /api/v1/auth/me': {
        status: 401,
        body: { error: { code: 'unauthorized', message: '请先登录', details: null } },
      },
    })
    const client = createApiClient({
      baseUrl: 'http://api.test',
      getToken: () => null,
      onUnauthorized,
      fetch,
    })
    const result = await client.GET('/api/v1/auth/me')
    expect(() => unwrap(result)).toThrowError(new ApiError(401, 'unauthorized', '请先登录'))
    expect(calls[0]?.authorization).toBeNull()
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })

  it('未传 baseUrl 时使用同源', () => {
    expect(createApiClient({ getToken: () => null })).toBeDefined()
  })
})
