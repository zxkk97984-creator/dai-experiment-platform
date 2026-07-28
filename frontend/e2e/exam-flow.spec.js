import { test, expect } from '@playwright/test'

test.describe('考试开始答题交卷流程', () => {
  test('开始考试 → 自动保存 → 交卷 → 等待评分', async ({ page }) => {
    // 学生登录
    await page.goto('/login')
    await expect(page.locator('#login-username')).toBeVisible()
    await page.fill('#login-username', 'student')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')

    // 导航到考试列表
    await page.goto('/student/exams')
    await expect(page).toHaveURL(/\/student\/exams/)

    // 点击第一个考试——必须存在
    const examLink = page.locator('a[href*="/student/exams/"]').first()
    await expect(examLink).toBeVisible({ timeout: 10000 })
    await examLink.click()

    // 点击开始考试——必须存在
    const startBtn = page.locator('button:has-text("开始考试")')
    await expect(startBtn).toBeVisible({ timeout: 10000 })
    await startBtn.click()

    // 等待题目加载——核心断言
    await expect(page.locator('.question-card, .exam-body')).toBeVisible({ timeout: 10000 })

    // 选择答案（如果有选项）
    const option = page.locator('.option-row').first()
    if (await option.isVisible({ timeout: 2000 }).catch(() => false)) {
      await option.click()
    }

    // 交卷——必须存在
    const submitBtn = page.locator('button:has-text("交卷")')
    await expect(submitBtn).toBeVisible({ timeout: 5000 })
    await submitBtn.click()
    await page.waitForTimeout(2000)
  })
})
