import { test, expect } from '@playwright/test'

test.describe('作业提交判题流程', () => {
  test('学生提交代码 → Worker 判题 → 查看结果', async ({ page }) => {
    // 学生登录
    await page.goto('/login')
    await expect(page.locator('#login-username')).toBeVisible()
    await page.fill('#login-username', 'student')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')

    // 导航到作业列表
    await page.goto('/student/assignments')
    await expect(page).toHaveURL(/\/student\/assignments/)

    // 点击第一个作业——必须存在
    const assignmentLink = page.locator('a[href*="/student/assignments/"]').first()
    await expect(assignmentLink).toBeVisible({ timeout: 10000 })
    await assignmentLink.click()

    // 代码编辑器——必须存在
    const editor = page.locator('textarea, .code-editor, [contenteditable]').first()
    await expect(editor).toBeVisible({ timeout: 10000 })
    await editor.fill('def add(a, b):\n    return a + b')

    // 提交按钮——必须存在
    const submitBtn = page.locator('button:has-text("提交")')
    await expect(submitBtn).toBeVisible()
    await submitBtn.click()

    // 等待判题结果——核心断言（匹配任一判题结果状态文本）
    await expect(page.getByText(/accepted|wrong_answer|runtime_error|time_limit/)).toBeVisible({ timeout: 30000 })
  })
})
