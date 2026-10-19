/** 375px 宽度（CLAUDE.md §8 M2）：各页面不出现整页横向滚动；表格在自身容器内滚动。 */
import { expect, test } from '@playwright/test'

import { ADMIN, ADMIN_PASSWORD } from './constants'
import { noHorizontalScroll, uiLogin } from './helpers'

test.use({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true })

test('375px 宽度下各页面可用', async ({ page }) => {
  await page.goto('/login')
  await noHorizontalScroll(page)
  await uiLogin(page, ADMIN, ADMIN_PASSWORD)
  await expect(page).toHaveURL(/\/$/)
  for (const path of ['/', '/preview', '/publications', '/review', '/admin', '/change-password']) {
    await page.goto(path)
    await page.waitForLoadState('networkidle')
    await noHorizontalScroll(page)
  }
  await page.goto('/preview')
  await page.getByTestId('pv-gpa').fill('3.6524')
  await page.getByTestId('pv-submit').click()
  await expect(page.getByTestId('pv-final')).toBeVisible()
  await noHorizontalScroll(page)
})
