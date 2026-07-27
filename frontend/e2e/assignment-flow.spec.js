import { test, expect } from '@playwright/test'

test.describe('作业提交判题流程', () => {
  test('学生提交代码 → Worker 判题 → 查看结果', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[name="username"]', 'student')
    await page.fill('input[name="password"]', 'Passw0rd!')
    await page.click('button[type="submit"]')

    // 导航到作业列表
    await page.goto('/student/assignments')
    await expect(page).toHaveURL(/\/student\/assignments/)

    // 点击第一个作业
    const assignmentLink = page.locator('a[href*="/student/assignments/"]').first()
    if (await assignmentLink.isVisible()) {
      await assignmentLink.click()
      // 在代码编辑器中输入代码
      const editor = page.locator('textarea, .code-editor, [contenteditable]').first()
      if (await editor.isVisible()) {
        await editor.fill('def add(a, b):\n    return a + b')
        await page.click('button:has-text("提交")')
        // 等待判题结果
        await expect(page.locator('text=accepted, text=wrong_answer, text=runtime_error')).toBeVisible({ timeout: 30000 })
      }
    }
  })
})
