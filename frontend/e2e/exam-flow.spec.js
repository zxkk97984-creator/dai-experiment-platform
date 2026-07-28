import { test, expect } from '@playwright/test'

test.describe('考试开始答题交卷流程', () => {
  test('开始考试 → 自动保存 → 交卷 → 等待评分', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('#login-username')).toBeVisible()
    await page.fill('#login-username', 'student')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/student\/courses/, { timeout: 10000 })
    await page.waitForTimeout(1000)

    // 导航到考试详情——页面必须加载成功
    await page.goto('/student/exams/1')
    await expect(page).toHaveURL(/\/student\/exams\/1/, { timeout: 15000 })

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
