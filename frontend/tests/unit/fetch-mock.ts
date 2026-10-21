import { vi } from 'vitest'

export interface Call {
  method: string
  url: string
  authorization: string | null
  body: unknown
}

type Reply = { status: number; body: unknown }

/** 按 “方法 路径” 返回预设响应，并记录每次请求。 */
export function mockFetch(routes: Record<string, Reply | Reply[]>) {
  const calls: Call[] = []
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new Request(input, init)
    const url = new URL(request.url)
    const text = await request.text()
    calls.push({
      method: request.method,
      url: url.pathname,
      authorization: request.headers.get('Authorization'),
      body: text ? JSON.parse(text) : null,
    })
    const entry = routes[`${request.method} ${url.pathname}`]
    const reply = Array.isArray(entry) ? entry.shift() : entry
    if (!reply) return new Response('not mocked', { status: 599 })
    return new Response(JSON.stringify(reply.body), {
      status: reply.status,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  return { fetch, calls }
}

export const student = {
  id: 2,
  username: 'TEST0002',
  name: '测试学生',
  class_name: '测试A班',
  roles: ['student'],
  must_change_password: false,
  is_active: true,
}
