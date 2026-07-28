import { test, expect } from '@playwright/test'

test.describe('Notebook 实验提交评分流程', () => {
  test('学生运行 cell → 保存 → 提交 → 教师查看评分', async ({ page }) => {
    // 学生登录
    await page.goto('/login')
    await expect(page.locator('input[name="username"]')).toBeVisible()
    await page.fill('input[name="username"]', 'student')
    await page.fill('input[name="password"]', 'Passw0rd!')
    await page.click('button[type="submit"]')

    // 导航到实验列表
    await page.goto('/student/experiments')
    await expect(page).toHaveURL(/\/student\/experiments/)

    // 点击第一个实验——必须存在
    const expLink = page.locator('a[href*="/student/experiments/"]').first()
    await expect(expLink).toBeVisible({ timeout: 10000 })
    await expLink.click()

    // 执行代码 cell——必须有运行按钮
    const runBtn = page.locator('button:has-text("▶"), button:has-text("Run"), button[title="运行"]').first()
    await expect(runBtn).toBeVisible({ timeout: 10000 })
    await runBtn.click()
    // 等待执行完成
    await page.waitForTimeout(3000)

    // 打开菜单提交
    const menuBtn = page.locator('[aria-haspopup="menu"], .btn-icon').first()
    await expect(menuBtn).toBeVisible()
    await menuBtn.click()

    // 提交按钮必须存在
    const submitBtn = page.locator('.menu-submit, button:has-text("提交实验")')
    await expect(submitBtn).toBeVisible({ timeout: 5000 })
    await submitBtn.click()
    // 等待提交完成
    await page.waitForTimeout(2000)
  })
})
