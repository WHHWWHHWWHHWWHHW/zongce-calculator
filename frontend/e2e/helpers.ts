import { type APIRequestContext, expect, type Page } from '@playwright/test'

import { ADMIN, ADMIN_PASSWORD, API } from './constants'

export async function apiLogin(request: APIRequestContext): Promise<Record<string, string>> {
  const response = await request.post(`${API}/auth/login`, {
    data: { username: ADMIN, password: ADMIN_PASSWORD },
  })
  expect(response.ok()).toBeTruthy()
  return { Authorization: `Bearer ${(await response.json()).access_token}` }
}

export function csv(name: string, text: string) {
  return { file: { name, mimeType: 'text/csv', buffer: Buffer.from(text, 'utf-8') } }
}

export async function uiLogin(page: Page, username: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()
  await expect(page).not.toHaveURL(/\/login/) // 等登录完成、离开登录页
}

/** 换一个账号登录：先清除当前页面的登录态（令牌存在 sessionStorage）。 */
export async function switchUser(page: Page, username: string, password: string): Promise<void> {
  if (page.url().startsWith('http')) await page.evaluate(() => sessionStorage.clear())
  await uiLogin(page, username, password)
}

/** 首次登录：用初始密码登录 → 强制改密 → 用新密码重新登录。 */
export async function firstLogin(page: Page, username: string, initial: string, next: string) {
  await uiLogin(page, username, initial)
  await expect(page).toHaveURL(/change-password/)
  await expect(page.getByText('首次登录请先修改初始密码')).toBeVisible()
  await page.getByTestId('pw-old').fill(initial)
  await page.getByTestId('pw-new').fill(next)
  await page.getByTestId('pw-confirm').fill(next)
  await page.getByTestId('pw-submit').click()
  await expect(page).toHaveURL(/login/)
  await uiLogin(page, username, next)
  await expect(page).toHaveURL(/\/$/)
}

/** 在 Element Plus 下拉框中选择一项。 */
export async function pick(page: Page, testId: string, text: string): Promise<void> {
  await page.getByTestId(testId).click()
  await page.locator('.el-select-dropdown__item:visible', { hasText: text }).first().click()
}

export async function noHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow, `页面出现横向滚动（多出 ${overflow}px）`).toBeLessThanOrEqual(0)
}
