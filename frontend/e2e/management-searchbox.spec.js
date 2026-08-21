import { test, expect } from '@playwright/test'

const managementPages = [
  { path: '/teacher/experiments', title: '实验模块管理', placeholder: '搜索实验名称' },
  { path: '/teacher/exams', title: '考试管理', placeholder: '搜索考试名称或课程' },
  { path: '/teacher/assignments', title: '作业管理', placeholder: '搜索作业名称' },
]

const studentPages = [
  { path: '/student/courses', title: '我的课程', placeholder: '搜索课程' },
  { path: '/student/experiments', title: '实验模块', placeholder: '搜索实验模块名称' },
]

test.describe('教师管理列表搜索框', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('#login-username', 'teacher')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/teacher(?:\/|$)/)
  })

  for (const { path, title, placeholder } of managementPages) {
    test(`${title}使用课程管理的标准搜索框`, async ({ page }) => {
      await page.goto(path)
      await expect(page.getByText(title, { exact: true }).first()).toBeVisible({ timeout: 15000 })

      const searchbox = page.locator('.searchbox')
      const input = searchbox.locator('input')
      await expect(searchbox).toHaveCount(1)
      await expect(input).toHaveAttribute('type', 'search')
      await expect(input).toHaveClass(/\binput\b/)
      await expect(input).toHaveAttribute('placeholder', placeholder)
      await expect(searchbox.locator(':scope > svg')).toHaveCSS('position', 'absolute')
      await expect(input).toHaveCSS('padding-left', '32px')

      await input.fill('测试')
      const clearButton = searchbox.getByRole('button', { name: '清空搜索' })
      const clearIcon = clearButton.locator('svg')
      await expect(clearButton).toBeVisible()
      await expect(clearIcon).toHaveCSS('width', '13px')
      await clearButton.hover()
      await expect(clearIcon).toHaveCSS('width', '13px')

      await clearButton.click()
      await expect(input).toHaveValue('')
      await expect(clearButton).toHaveCount(0)
    })
  }
})

test.describe('学生列表搜索框', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('#login-username', 'student')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/student(?:\/|$)/)
  })

  for (const { path, title, placeholder } of studentPages) {
    test(`${title}使用课程管理的标准搜索框`, async ({ page }) => {
      await page.goto(path)
      await expect(page.getByText(title, { exact: true }).first()).toBeVisible({ timeout: 15000 })

      const searchbox = page.locator('.searchbox')
      const input = searchbox.locator('input')
      await expect(searchbox).toHaveCount(1)
      await expect(input).toHaveAttribute('type', 'search')
      await expect(input).toHaveClass(/\binput\b/)
      await expect(input).toHaveAttribute('placeholder', placeholder)
      await expect(searchbox.locator(':scope > svg')).toHaveCSS('position', 'absolute')
      await expect(input).toHaveCSS('padding-left', '32px')

      await input.fill('测试')
      const clearButton = searchbox.getByRole('button', { name: /清空.*搜索/ })
      const clearIcon = clearButton.locator('svg')
      await expect(clearButton).toBeVisible()
      await expect(clearIcon).toHaveCSS('width', '13px')
      await clearButton.hover()
      await expect(clearIcon).toHaveCSS('width', '13px')

      await clearButton.click()
      await expect(input).toHaveValue('')
      await expect(clearButton).toHaveCount(0)
    })
  }
})
