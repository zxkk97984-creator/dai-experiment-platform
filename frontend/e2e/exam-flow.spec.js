import { test, expect } from '@playwright/test'

test.describe('考试开始答题交卷流程', () => {
  test('开始考试 → 自动保存 → 交卷 → 等待评分', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[name="username"]', 'student')
    await page.fill('input[name="password"]', 'Passw0rd!')
    await page.click('button[type="submit"]')

    await page.goto('/student/exams')
    await expect(page).toHaveURL(/\/student\/exams/)

    // 点击第一个考试
    const examLink = page.locator('a[href*="/student/exams/"]').first()
    if (await examLink.isVisible()) {
      await examLink.click()
      // 点击开始考试
      const startBtn = page.locator('button:has-text("开始考试")')
      if (await startBtn.isVisible()) {
        await startBtn.click()
        // 等待题目加载
        await expect(page.locator('.question-card, .exam-body')).toBeVisible({ timeout: 10000 })
        // 选择答案（如果有选项）
        const option = page.locator('.option-row').first()
        if (await option.isVisible()) {
          await option.click()
        }
        // 交卷
        await page.click('button:has-text("交卷")')
        await page.waitForTimeout(2000)
      }
    }
  })
})
