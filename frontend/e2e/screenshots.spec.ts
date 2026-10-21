/**
 * 演示截图（中期检查材料，CLAUDE.md §8 M2）。设置 SCREENSHOTS_DIR 时才运行，依赖 flow.spec 造好的合成数据。
 * 用法：SCREENSHOTS_DIR=../docs/reports/screenshots pnpm test:e2e
 */
import { type APIRequestContext, expect, type Page, test } from '@playwright/test'

import { ADMIN, ADMIN_PASSWORD, API, REVIEWER_PASSWORD, STUDENT_PASSWORD } from './constants'
import { switchUser, uiLogin } from './helpers'

const dir = process.env.SCREENSHOTS_DIR
test.skip(!dir, '未设置 SCREENSHOTS_DIR，跳过截图')

async function shot(page: Page, name: string): Promise<void> {
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: `${dir}/${name}.png`, fullPage: true })
}

/** 再准备两条待审申报，让审核工作台能展示标红：申报分≠建议分；需人工给分且未上传材料。 */
async function pendingDeclarations(request: APIRequestContext): Promise<void> {
  const login = await request.post(`${API}/auth/login`, {
    data: { username: 'TEST0002', password: STUDENT_PASSWORD },
  })
  const headers = { Authorization: `Bearer ${(await login.json()).access_token}` }
  const bodies = [
    {
      catalog_code: 'competition',
      option_code: 'c2_provincial_2',
      title: '省级大学生程序设计竞赛二等奖（3 人第 1 位）',
      team_size: 3,
      team_position: 1,
      claimed_score: '10',
    },
    { catalog_code: 'outstanding_deeds', title: '协助处理校园突发事件', claimed_score: '3' },
  ]
  for (const body of bodies) {
    const created = await request.post(`${API}/declarations`, {
      headers,
      data: { year_id: 1, ...body },
    })
    expect(created.status()).toBe(201)
    const id = (await created.json()).id
    if (body.catalog_code === 'competition') {
      await request.post(`${API}/declarations/${id}/evidence`, {
        headers,
        multipart: {
          file: {
            name: '获奖证书.pdf',
            mimeType: 'application/pdf',
            buffer: Buffer.from('%PDF-1.4'),
          },
        },
      })
    }
    await request.post(`${API}/declarations/${id}/submit`, { headers })
  }
}

test('桌面端截图', async ({ page, request }) => {
  await pendingDeclarations(request)
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/login')
  await shot(page, '01-登录')
  await uiLogin(page, 'TEST0002', STUDENT_PASSWORD)
  await page.goto('/my/declarations')
  await shot(page, '02-学生-我的申报')
  await page.goto('/my/scores')
  await shot(page, '03-学生-我的成绩')
  await page.goto('/preview')
  await page.getByTestId('pv-gpa').fill('3.6524')
  await page.getByTestId('pv-political').fill('9.5')
  await page.getByTestId('pv-ability').fill('38')
  await page.getByTestId('pv-submit').click()
  await page.getByTestId('pv-final').waitFor()
  await shot(page, '04-成绩预估')

  await switchUser(page, 'TEST0001', REVIEWER_PASSWORD)
  await page.goto('/review')
  await expect(page.locator('.row-discrepant')).toHaveCount(2)
  await shot(page, '05-审核工作台')

  await switchUser(page, ADMIN, ADMIN_PASSWORD)
  await page.goto('/admin')
  await shot(page, '06-管理后台-学年与规则')
  await page.getByRole('tab', { name: '核算与排名' }).click()
  await shot(page, '07-管理后台-核算与排名')
})

test('手机端截图（375px）', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await uiLogin(page, 'TEST0002', STUDENT_PASSWORD)
  await page.goto('/my/declarations')
  await shot(page, '08-手机-我的申报')
  await page.goto('/my/scores')
  await shot(page, '09-手机-我的成绩')
})
