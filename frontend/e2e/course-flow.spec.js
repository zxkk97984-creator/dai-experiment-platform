import { test, expect } from '@playwright/test'

test.describe('课程学习主流程', () => {
  test('学生登录、选课、阅读课时', async ({ page }) => {
    // 学生登录
    await page.goto('/login')
    await expect(page.locator('#login-username')).toBeVisible()
    await page.fill('#login-username', 'student')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')

    // 登录后应跳转到课程列表
    await expect(page).toHaveURL(/\/student\/courses/)

    // 点击第一门课程——必须存在
    const courseCard = page.locator('.course-card, [data-test="course-item"]').first()
    await expect(courseCard).toBeVisible({ timeout: 10000 })
    await courseCard.click()

    // 应跳转到课程详情页
    await expect(page).toHaveURL(/\/student\/courses\/\d+/)
  })
})
