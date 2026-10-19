import { defineConfig, devices } from '@playwright/test'

import { ADMIN_PASSWORD, API_PORT, WEB_PORT } from './e2e/constants'

// 浏览器可执行文件：默认用 Playwright 自带的；本机无法下载时可用 PW_CHROMIUM 指定已安装的 Chromium
const executablePath = process.env.PW_CHROMIUM

export default defineConfig({
  testDir: 'e2e',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1, // 所有用例共用同一个后端数据库，按顺序执行
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: executablePath ? { executablePath } : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'bash e2e/start-api.sh',
      url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
      env: { E2E_ADMIN_PASSWORD: ADMIN_PASSWORD, E2E_API_PORT: String(API_PORT) },
      timeout: 180_000,
      stdout: 'pipe',
    },
    {
      command: `pnpm exec vite preview --port ${WEB_PORT} --strictPort`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: { VITE_PROXY_TARGET: `http://127.0.0.1:${API_PORT}` },
      timeout: 60_000,
    },
  ],
})
