import { test, expect } from '@playwright/test'

test.describe('作业提交判题流程', () => {
  test('学生提交代码 → Worker 判题 → 查看结果', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('#login-username')).toBeVisible()
    await page.fill('#login-username', 'student')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/student\/courses/, { timeout: 10000 })
    await page.waitForTimeout(1000)

    // 导航到作业详情
    await page.goto('/student/assignments/1')
    await expect(page).toHaveURL(/\/student\/assignments\/1/, { timeout: 15000 })

    // 代码编辑器存在
    const editor = page.locator('textarea, .code-editor, [contenteditable]').first()
    await expect(editor).toBeVisible({ timeout: 10000 })
    await editor.fill('def add(a, b):\n    return a + b')

    // 提交代码——使用具体按钮文本
    await page.getByRole('button', { name: '提交代码' }).click()

    // 等待判题结果出现
    await expect(page.getByText(/accepted|wrong_answer|runtime_error|判题/)).toBeVisible({ timeout: 30000 })
  })
})
