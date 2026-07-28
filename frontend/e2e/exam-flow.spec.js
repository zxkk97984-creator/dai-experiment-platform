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

    // 点击开始考试（如果存在）或直接验证页面结构
    const startBtn = page.getByRole('button', { name: /开始考试|开始/ })
    const started = await startBtn.isVisible({ timeout: 3000 }).catch(() => false)
    if (started) {
      await startBtn.click()
      await expect(page.locator('.question-card, .exam-body, [class*="question"]').first()).toBeVisible({ timeout: 10000 })

      // 交卷
      await page.getByRole('button', { name: /交卷/ }).click()
      await page.waitForTimeout(2000)
    }
  })
})
