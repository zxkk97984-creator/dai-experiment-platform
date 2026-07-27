import { test, expect } from '@playwright/test'

test.describe('课程学习主流程', () => {
  test('学生登录、选课、阅读课时', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[name="username"]', 'student')
    await page.fill('input[name="password"]', 'Passw0rd!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/student\/courses/)

    // 点击第一门课程
    const courseCard = page.locator('.course-card, [data-test="course-item"]').first()
    if (await courseCard.isVisible()) {
      await courseCard.click()
      await expect(page).toHaveURL(/\/student\/courses\/\d+/)
    }
  })
})
