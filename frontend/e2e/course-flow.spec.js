import { test, expect } from '@playwright/test'

test.describe('课程学习主流程', () => {
  test('学生登录、选课、阅读课时', async ({ page }) => {
    // 学生登录
    await page.goto('/login')
    await expect(page.locator('#login-username')).toBeVisible()
    await page.fill('#login-username', 'student')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')

    // 登录后进入新版学生首页（/student），显式导航到课程列表
    await expect(page).toHaveURL(/\/student(?:\/|$)/)
    await page.goto('/student/courses')
    await expect(page).toHaveURL(/\/student\/courses$/)

    // 点击第一门课程——必须存在（列表项为 .course-row，入口为 .course-row-link）
    const courseCard = page.locator('.course-row').first()
    await expect(courseCard).toBeVisible({ timeout: 10000 })
    await courseCard.locator('.course-row-link').click()

    // 应跳转到课程详情页
    await expect(page).toHaveURL(/\/student\/courses\/\d+/)

    // 切换到「章节内容」标签后打开第一课并实际读取课时内容
    await page.locator('.course-tab', { hasText: '章节内容' }).click()
    await page.locator('button.chapter-row').first().click()
    await expect(page).toHaveURL(/\/student\/courses\/\d+\/lessons\/\d+/)
    await expect(page.getByText('测试课时')).toBeVisible()
  })
})
