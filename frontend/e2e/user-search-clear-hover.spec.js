import { test, expect } from '@playwright/test'

test.describe('管理员用户搜索框', () => {
  test('清空按钮悬停时保持图标可见', async ({ page }) => {
    await page.goto('/login')
    await page.fill('#login-username', 'admin')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/admin(?:\/|$)/)

    await page.goto('/admin/users')
    const input = page.locator('input[aria-label="搜索用户名、学号或姓名"]')
    await input.fill('asa')
    expect(await input.evaluate((element) => getComputedStyle(element).getPropertyValue('-webkit-appearance'))).toBe('none')

    const clearButton = page.getByRole('button', { name: '清空搜索' })
    const icon = clearButton.locator('svg')
    await expect(clearButton).toBeVisible()
    await expect(icon).toHaveCSS('width', '13px')

    await clearButton.hover()
    await expect(clearButton).toBeVisible()
    await expect(icon).toHaveCSS('width', '13px')
  })
})
