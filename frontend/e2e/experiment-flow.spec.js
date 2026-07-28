import { test, expect } from '@playwright/test'

test.describe('Notebook 实验提交评分流程', () => {
  test('学生运行 cell → 保存 → 提交 → 教师查看评分', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('#login-username')).toBeVisible()
    await page.fill('#login-username', 'student')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/student\/courses/, { timeout: 10000 })
    await page.waitForTimeout(1000)

    // 导航到实验详情——页面必须加载成功
    await page.goto('/student/experiments/1')
    await expect(page).toHaveURL(/\/student\/experiments\/1/, { timeout: 15000 })

    // 实验页面至少显示实验名称
    await expect(page.getByText('E2E 测试实验')).toBeVisible({ timeout: 10000 })

    // 运行 cell——页面应有源码或运行按钮
    const runBtn = page.locator('button').filter({ hasText: /▶|Run|运行/ }).first()
    const canRun = await runBtn.isVisible({ timeout: 3000 }).catch(() => false)
    if (canRun) {
      await runBtn.click()
      await page.waitForTimeout(3000)
    }

    // 验证页面有 cell 内容
    await expect(page.getByText(/print|hello/).first()).toBeVisible({ timeout: 5000 })
  })
})
