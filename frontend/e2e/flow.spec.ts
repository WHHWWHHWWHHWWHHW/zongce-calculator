/**
 * 端到端主流程（CLAUDE.md §8 M2）：学生申报 → 审核员通过 → 管理员核算并导出。
 * 只使用合成数据（学号以 TEST 开头）。
 */
import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import { API, REVIEWER_PASSWORD, STUDENT_PASSWORD } from './constants'
import { apiLogin, csv, firstLogin, pick, uiLogin } from './helpers'

const passwords: Record<string, string> = {}

test.describe.configure({ mode: 'serial' })

test('管理员准备学年、账号与学院成绩表（API）', async ({ request }) => {
  const headers = await apiLogin(request)
  const year = await request.post(`${API}/years`, {
    headers,
    data: { name: '2025-2026', rule_version_id: 1 },
  })
  expect(year.status()).toBe(201)
  const yearId = (await year.json()).id
  await request.patch(`${API}/years/${yearId}/status`, { headers, data: { status: 'open' } })

  const users = await request.post(`${API}/users/import`, {
    headers,
    multipart: csv(
      'users.csv',
      '学号,姓名,班级,角色\nTEST0001,测试审核员,测试1班,学生、班级审核员\nTEST0002,测试学生,测试1班,学生\n',
    ),
  })
  const created = (await users.json()).created as { username: string; initial_password: string }[]
  for (const c of created) passwords[c.username] = c.initial_password
  expect(Object.keys(passwords).sort()).toEqual(['TEST0001', 'TEST0002'])

  // G1 的各项成绩（能力分来自申报，不在表中）
  const college = await request.post(`${API}/years/${yearId}/college-data/import`, {
    headers,
    multipart: csv(
      'college.csv',
      '学号,学分绩点,第二课堂,公益劳动,体测成绩,宿舍成绩,政治素养,品德修养,纪律观念,诚信评价\n' +
        'TEST0002,3.6524,2.5,4,85,92,"9,8.5,10,7,9.5,8,9,10,6.5,8",9.5,4.5,5\n',
    ),
  })
  expect((await college.json()).errors).toEqual([])
})

test('学生首次登录改密，申报并上传材料后提交', async ({ page }) => {
  await firstLogin(page, 'TEST0002', passwords.TEST0002!, STUDENT_PASSWORD)
  await page.locator('.el-menu-item', { hasText: '我的申报' }).click()
  await expect(page).toHaveURL(/my\/declarations/)

  await page.getByTestId('decl-new').click()
  await pick(page, 'decl-item', '校级荣誉称号')
  await pick(page, 'decl-option', '十佳团员')
  await page.getByTestId('decl-title').fill('济南大学十佳团员')
  await page.getByTestId('decl-claimed').fill('6') // 与建议分 5 不一致，审核时应标红
  await page.getByTestId('decl-save').click()
  const row = page
    .getByTestId('decl-table')
    .locator('.el-table__row', { hasText: '济南大学十佳团员' })
  await expect(row).toContainText('5.0000')
  await expect(row).toContainText('草稿')

  await row.getByRole('button', { name: /材料/ }).first().click()
  await page.locator('.el-dialog .el-upload__input').setInputFiles({
    name: '证书.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4\n%synthetic\n'),
  })
  await expect(page.locator('.el-dialog').getByText('证书.pdf')).toBeVisible()
  await page.keyboard.press('Escape')

  await row.getByTestId('decl-submit').first().click()
  await page.locator('.el-message-box').getByRole('button', { name: '确定' }).click()
  await expect(row).toContainText('待审核')
})

test('审核员在工作台看到标红的申报并通过', async ({ page }) => {
  await firstLogin(page, 'TEST0001', passwords.TEST0001!, REVIEWER_PASSWORD)
  await page.locator('.el-menu-item', { hasText: '审核工作台' }).click()
  const row = page.getByTestId('review-table').locator('.el-table__row', { hasText: '测试学生' })
  await expect(row).toHaveClass(/row-discrepant/)
  await expect(row).toContainText('申报分与建议分不一致')

  await row.getByTestId('review-approve').first().click()
  await page.getByTestId('review-reason').fill('材料齐全，按细则建议分通过')
  await page.getByTestId('review-confirm').click()
  await page.getByTestId('year-select').click()
  await page.keyboard.press('Escape')
  await expect(page.locator('.el-message--success')).toContainText('已通过')
})

test('管理员核算并导出 Excel；学生看到综测成绩', async ({ page, browser }) => {
  await uiLogin(page, 'e2eadmin', 'E2eAdmin12345')
  await page.locator('.el-menu-item', { hasText: '管理后台' }).click()
  await page.getByRole('tab', { name: '核算与排名' }).click()
  await page.getByTestId('compute').click()
  await expect(page.locator('.el-message--success')).toContainText('已核算 2 人')
  await expect(page.locator('.el-table__row', { hasText: 'TEST0002' })).toContainText('3.3127')

  const [response, download] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/rankings/export')),
    page.waitForEvent('download'),
    page.getByTestId('export').click(),
  ])
  expect(decodeURIComponent(response.headers()['content-disposition'] ?? '')).toContain(
    '2025-2026-综测排名.xlsx',
  )
  const bytes = readFileSync((await download.path())!)
  expect(bytes.subarray(0, 2).toString('latin1')).toBe('PK') // xlsx 是 ZIP 格式
  // 用 PW_CHROMIUM 指定的非配套 Chromium 不回报文件名（总是 “download”），只在配套浏览器上检查
  if (!process.env.PW_CHROMIUM) expect(download.suggestedFilename()).toMatch(/综测排名\.xlsx$/)

  const student = await browser.newPage()
  await uiLogin(student, 'TEST0002', STUDENT_PASSWORD)
  await student.locator('.el-menu-item', { hasText: '我的成绩' }).click()
  // G1 数据 + 审核通过的能力分 5：(27.625 + 13.25 + 5) ÷ 20 × 25% + 3.6524 × 75% = 3.3127375
  await expect(student.getByTestId('my-final')).toHaveText('3.3127')
})
