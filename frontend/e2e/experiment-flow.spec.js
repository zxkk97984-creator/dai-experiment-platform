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

    // 运行 cell，按钮必须存在
    const runBtn = page.locator('button').filter({ hasText: /▶|Run|运行/ }).first()
    await expect(runBtn).toBeVisible()
    await runBtn.click()

    // 等待 Kernel 完成并把输出保存到 record 后再提交
    await expect(page.locator('.exec-count')).toHaveText('In [1]', { timeout: 30000 })
    await expect(page.locator('.output-area')).toContainText('hello e2e')

    // 打开操作菜单并提交，必须出现提交成功状态
    await page.locator('[aria-haspopup="menu"]').click()
    await page.locator('.menu-submit').click()
    await expect(page.locator('.submit-status.submitted')).toBeVisible({ timeout: 10000 })

    // 管理员进入提交详情并完成评分，覆盖教师端同一套评阅界面
    await page.evaluate(() => localStorage.clear())
    await page.goto('/login')
    await page.fill('#login-username', 'admin')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/admin\//)

    await page.goto('/admin/submissions')
    await page.locator('.submission-card').first().click()
    await expect(page).toHaveURL(/\/admin\/submissions\/\d+/)
    await expect(page.getByText('提交快照（只读）')).toBeVisible()
    await expect(page.getByText(/execution_count:\s*1/)).toBeVisible()
    await page.locator('input[type="number"]').fill('95')
    await page.locator('textarea').fill('E2E 评分通过')
    await page.getByRole('button', { name: '保存评分' }).click()
    await expect(page.getByText(/上次评分/)).toBeVisible({ timeout: 10000 })
  })
})
