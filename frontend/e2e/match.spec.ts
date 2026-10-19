/**
 * 名单比对（CLAUDE.md §8 M4 基础）：审核员上传学院获奖名单 → 系统给出建议 → 审核员勾选确认。
 * 依赖 flow.spec.ts 建好的学年与账号；只使用合成数据。
 */
import { expect, test } from '@playwright/test'

import { API, REVIEWER_PASSWORD, STUDENT_PASSWORD } from './constants'
import { pick, uiLogin } from './helpers'

test('审核员上传获奖名单，确认可快速通过的申报', async ({ page, request }) => {
  const login = await request.post(`${API}/auth/login`, {
    data: { username: 'TEST0002', password: STUDENT_PASSWORD },
  })
  const headers = { Authorization: `Bearer ${(await login.json()).access_token}` }
  const yearId = (await (await request.get(`${API}/years`, { headers })).json())[0].id
  const created = await request.post(`${API}/declarations`, {
    headers,
    data: {
      year_id: yearId,
      catalog_code: 'competition',
      option_code: 'c1_provincial_1',
      title: '某学科竞赛省级一等奖',
    },
  })
  const declarationId = (await created.json()).id
  await request.post(`${API}/declarations/${declarationId}/submit`, { headers })

  await uiLogin(page, 'TEST0001', REVIEWER_PASSWORD)
  await page.locator('.el-menu-item', { hasText: '名单比对' }).click()
  await expect(page).toHaveURL(/review\/match/)
  await expect(page.getByText('目前只支持表格')).toBeVisible()
  await pick(page, 'match-item', '专业类或学术性竞赛')
  await page.getByTestId('match-context').fill('一类赛事')
  await page.locator('.el-upload__input').setInputFiles({
    name: '竞赛获奖名单.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(
      '学号,姓名,获奖级别,获奖等级\nTEST0002,测试学生,省级,一等奖\nTEST0999,某人,省级,二等奖\n',
      'utf-8',
    ),
  })

  const table = page.getByTestId('match-table')
  const consistent = table.locator('.el-table__row', { hasText: 'TEST0002' })
  await expect(consistent).toContainText('与申报一致')
  await expect(consistent).toContainText('可快速通过')
  await expect(table.locator('.el-table__row', { hasText: 'TEST0999' })).toContainText('学号不存在')

  await page.getByTestId('match-confirm').click() // 可快速通过的行已默认勾选
  await expect(page.locator('.el-message--success')).toContainText('已通过 1 条')
  await expect(consistent).toContainText('已通过')

  const after = await request.get(`${API}/declarations/${declarationId}`, { headers })
  expect((await after.json()).status).toBe('approved')
})
