import { test, expect } from '@playwright/test'

test.describe('考试开始答题交卷流程', () => {
  test('开始考试 → 自动保存 → 交卷 → 等待评分', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('#login-username')).toBeVisible()
    await page.fill('#login-username', 'student')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/student(?:\/|$)/, { timeout: 10000 })
    await page.waitForTimeout(1000)

    // 导航到考试详情（从列表动态进入，不依赖固定 id）——页面必须加载成功
    await page.goto('/student/exams')
    await expect(page).toHaveURL(/\/student\/exams$/, { timeout: 15000 })
    await page.locator('article', { hasText: 'E2E 测试考试' }).first().click()
    await expect(page).toHaveURL(/\/student\/exams\/\d+/, { timeout: 15000 })

    // 考试页面至少显示标题
    await expect(page.getByText('E2E 测试考试')).toBeVisible({ timeout: 10000 })

    // 新种子数据库中必须能够开始考试
    const startBtn = page.getByRole('button', { name: /开始考试|开始/ })
    await expect(startBtn).toBeVisible()
    await startBtn.click()
    await expect(page.locator('.question-card').first()).toBeVisible({ timeout: 10000 })

    // 选择正确答案 B，并确认交卷
    await page.locator('.option-row').filter({ hasText: 'B.' }).click()
    page.once('dialog', dialog => dialog.accept())
    await page.getByRole('button', { name: /交卷/ }).click()
    await expect(page.locator('.result-card')).toContainText(/已交卷|已评分/, { timeout: 10000 })
  })
})

test.describe('成绩详情打印（教师）', () => {
  test('成绩详情提供打印/保存 PDF，无失效的导出报告按钮', async ({ page }) => {
    await page.goto('/login')
    await page.fill('#login-username', 'teacher')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/teacher(?:\/|$)/)

    // 从考试管理页进入 E2E 测试考试的成绩总览（不依赖固定 id）
    await page.goto('/teacher/exams')
    await expect(page.getByText('考试管理')).toBeVisible({ timeout: 15000 })
    await page.locator('tr', { hasText: 'E2E 测试考试' }).getByRole('button', { name: '成绩分析' }).click()
    await expect(page.getByText(/成绩总览/)).toBeVisible({ timeout: 15000 })

    const detailBtn = page.getByRole('button', { name: '查看详情' }).first()
    await expect(detailBtn).toBeVisible({ timeout: 10000 })
    await detailBtn.click()

    await expect(page.getByText('学生成绩详情')).toBeVisible({ timeout: 10000 })
    // 失效的「导出报告」按钮已移除；打印按钮支持浏览器打印与另存为 PDF
    await expect(page.getByRole('button', { name: /导出报告/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /打印 \/ 保存 PDF/ })).toBeVisible()
  })
})
