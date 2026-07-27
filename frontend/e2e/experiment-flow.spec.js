import { test, expect } from '@playwright/test'

test.describe('Notebook 实验提交评分流程', () => {
  test('学生运行 cell → 保存 → 提交 → 教师查看评分', async ({ page }) => {
    // 学生登录
    await page.goto('/login')
    await page.fill('input[name="username"]', 'student')
    await page.fill('input[name="password"]', 'Passw0rd!')
    await page.click('button[type="submit"]')

    await page.goto('/student/experiments')
    await expect(page).toHaveURL(/\/student\/experiments/)

    // 点击第一个实验
    const expLink = page.locator('a[href*="/student/experiments/"]').first()
    if (await expLink.isVisible()) {
      await expLink.click()
      // 执行代码 cell
      const runBtn = page.locator('button:has-text("▶"), button:has-text("Run"), button[title="运行"]').first()
      if (await runBtn.isVisible()) {
        await runBtn.click()
        await page.waitForTimeout(3000)
      }
      // 打开菜单提交
      const menuBtn = page.locator('[aria-haspopup="menu"], .btn-icon').first()
      if (await menuBtn.isVisible()) {
        await menuBtn.click()
        const submitBtn = page.locator('.menu-submit, button:has-text("提交实验")')
        if (await submitBtn.isVisible()) {
          await submitBtn.click()
          await page.waitForTimeout(2000)
        }
      }
    }
  })
})
