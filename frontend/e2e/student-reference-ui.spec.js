// 学生参考 UI 非破坏冒烟：
// 登录 → 首页 / 课程列表 / 课程详情 / 任务中心 / 反馈页；
// 练习标签、搜索、筛选、用户菜单、侧栏折叠、主导航；
// 绝不提交作业、考试、实验、公告或选课；
// 任何未捕获页面错误、console 错误、404 或 500 都会使测试失败。
import { test, expect } from '@playwright/test'

test.describe('学生参考 UI 冒烟（非破坏）', () => {
  const errors = []

  test.beforeEach(async ({ page }) => {
    errors.length = 0
    page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`))
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(`console: ${msg.text()}`)
    })
    page.on('response', (res) => {
      if (res.status() >= 400) errors.push(`http ${res.status()}: ${res.url()}`)
    })
  })

  test('五个学生路由可导航且无 404/500', async ({ page }) => {
    // ── 登录 ──────────────────────────────────────────────────
    await page.goto('/login')
    await page.fill('#login-username', 'student_24621600_01')
    await page.fill('#login-password', 'Test1234!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/student$/, { timeout: 15000 })

    // ── 首页：摘要卡与续学面板就绪 ────────────────────────────
    await expect(page.locator('.summary-cards')).toBeVisible({ timeout: 15000 })

    // 用户菜单：打开 → Escape 关闭
    await page.click('.user-trigger')
    await expect(page.locator('.user-menu')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.locator('.user-menu')).toHaveCount(0)

    // 侧栏折叠与展开
    await page.click('.collapse-btn')
    await expect(page.locator('.sidebar')).toHaveClass(/collapsed/)
    await page.click('.collapse-btn')
    await expect(page.locator('.sidebar')).not.toHaveClass(/collapsed/)

    // ── 我的课程 ──────────────────────────────────────────────
    await page.click('button.nav-item[aria-label="课程"]')
    await expect(page).toHaveURL(/\/student\/courses$/)
    await expect(page.locator('.page-title')).toContainText('我的课程')
    const firstRow = page.locator('.course-row').first()
    await expect(firstRow).toBeVisible()

    // 搜索过滤（客户端）
    const firstTitle = (await page.locator('.course-row-link .course-identity__title').first().textContent()) || ''
    await page.fill('.search-input', firstTitle.trim())
    await expect(page.locator('.course-row')).toHaveCount(1)
    await page.fill('.search-input', '')

    // 状态标签页
    await page.locator('.tab-btn', { hasText: '进行中' }).first().click()
    await page.locator('.tab-btn', { hasText: '全部课程' }).first().click()

    // ── 课程详情 ──────────────────────────────────────────────
    await page.locator('.course-row-link').first().click()
    await expect(page).toHaveURL(/\/student\/courses\/\d+/)
    await expect(page.locator('.course-tabs')).toBeVisible()

    // 标签切换（概览 ↔ 作业），不改变课程身份
    await page.locator('.course-tab', { hasText: '作业' }).click()
    await page.locator('.course-tab', { hasText: '概览' }).click()
    await expect(page.locator('.overview-grid')).toBeVisible()

    // ── 任务中心 ──────────────────────────────────────────────
    await page.click('button.nav-item[aria-label="作业"]')
    await expect(page).toHaveURL(/\/student\/assignments$/)
    await expect(page.locator('.status-tabs')).toBeVisible()
    await page.locator('.status-tab', { hasText: '逾期' }).click()
    await page.locator('.status-tab', { hasText: '全部' }).click()
    await page.selectOption('.filter-sort', 'due')
    await page.click('.reset-btn')

    // ── 反馈页 ────────────────────────────────────────────────
    await page.goto('/student/feedback')
    await expect(page).toHaveURL(/\/student\/feedback$/)
    await expect(page.locator('.page-title')).toContainText('提交与反馈')
    await expect(page.locator('.status-tabs')).toBeVisible()
    await expect(page.locator('.page-footer')).toBeVisible()

    // 侧栏 /student/feedback 高亮首页（镜像参考图 01）
    await expect(page.locator('button.nav-item[aria-label="首页"]')).toHaveClass(/active/)

    // ── 汇总断言：零 404/500、零页面错误、零 console 错误 ──────
    const httpErrors = errors.filter((e) => /^http (404|500)/.test(e))
    expect(httpErrors).toEqual([])
    const pageErrors = errors.filter((e) => /^(pageerror|console)/.test(e))
    expect(pageErrors).toEqual([])
  })

  test('实验目录快速连续搜索保留最新结果（防抖与防竞态）', async ({ page }) => {
    await page.goto('/login')
    await page.fill('#login-username', 'student_24621600_01')
    await page.fill('#login-password', 'Test1234!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/student$/, { timeout: 15000 })

    await page.goto('/student/experiments')
    await expect(page.getByRole('heading', { name: '实验模块', exact: true })).toBeVisible({ timeout: 15000 })

    const searchBox = page.locator('.search-box input')
    await expect(searchBox).toBeVisible()

    // 快速连续输入：中间词会触发请求，但最终结果必须对应最后输入
    await searchBox.fill('不存在的实验关键词xyz')
    await page.waitForTimeout(100)
    await searchBox.fill('')

    // 清空后应回到全部列表（最新请求结果胜出，旧结果不覆盖）
    await expect(page.getByText('全部实验模块')).toBeVisible({ timeout: 10000 })
    await expect(page.getByText(/共 \d+ 个/)).toBeVisible({ timeout: 10000 })
  })
})
