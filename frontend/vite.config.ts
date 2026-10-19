import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    // 本机开发：前端 5173，后端 `uv run zongce serve`（8000）
    proxy: { '/api': process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:8000' },
  },
  test: {
    environment: 'jsdom',
    // Node 的 fetch 不接受相对地址，测试中给 API 一个绝对地址
    env: { VITE_API_BASE: 'http://api.test' },
    globals: true,
    include: ['tests/unit/**/*.spec.ts'],
    exclude: ['e2e/**', 'node_modules/**'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.ts'],
      exclude: ['src/api/schema.d.ts', 'src/main.ts'],
      thresholds: { lines: 80, branches: 80, functions: 80, statements: 80 },
    },
  },
})
