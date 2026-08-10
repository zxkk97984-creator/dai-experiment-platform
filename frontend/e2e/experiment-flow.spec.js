import { test, expect } from '@playwright/test'

test.describe('Notebook 实验提交评分流程', () => {
  test('学生运行 cell → 保存 → 提交 → 教师查看评分', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('#login-username')).toBeVisible()
    await page.fill('#login-username', 'student')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/student(?:\/|$)/, { timeout: 10000 })
    await page.waitForTimeout(1000)

    // 导航到实验详情（从列表动态进入，不依赖固定 id）——页面必须加载成功
    await page.goto('/student/experiments')
    await expect(page).toHaveURL(/\/student\/experiments$/, { timeout: 15000 })
    await page.locator('tr', { hasText: 'E2E 测试实验' }).locator('.enter-button').click()
    await expect(page).toHaveURL(/\/student\/experiments\/\d+/, { timeout: 15000 })

    // 实验页面至少显示实验名称
    await expect(page.getByText('E2E 测试实验')).toBeVisible({ timeout: 10000 })

    // 运行 cell，按钮必须存在
    const runBtn = page.locator('button').filter({ hasText: /▶|Run|运行/ }).first()
    await expect(runBtn).toBeVisible()
    await runBtn.click()

    // 等待 Kernel 完成并把输出保存到 record 后再提交（计数随会话复用递增，用正则匹配）
    await expect(page.locator('.exec-count')).toHaveText(/In \[\d+\]/, { timeout: 30000 })
    await expect(page.locator('.output-area')).toContainText('hello e2e')

    // 打开操作菜单并提交，必须出现提交成功状态
    await page.getByRole('button', { name: '更多操作' }).click()
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
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
    // 进入刚提交的 E2E 提交详情（表格行内「去评分」操作）
    await page.locator('tbody tr', { hasText: 'E2E 测试实验' }).first()
      .getByRole('button', { name: '去评分' }).click()
    await expect(page).toHaveURL(/\/admin\/submissions\/\d+/)
    await expect(page.getByText('学生提交内容')).toBeVisible()
    await expect(page.getByText("print('hello e2e')")).toBeVisible()
    await expect(page.getByText('hello e2e', { exact: true })).toBeVisible()
    await page.locator('#review-score').fill('95')
    await page.locator('#review-feedback').fill('E2E 评分通过')
    await page.getByRole('button', { name: '保存评分' }).click()
    await expect(page.getByText(/上次保存于/)).toBeVisible({ timeout: 10000 })
  })
})

test.describe('实验模块管理（教师）', () => {
  async function loginTeacher(page) {
    await page.goto('/login')
    await page.fill('#login-username', 'teacher')
    await page.fill('#login-password', 'Passw0rd!')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/teacher(?:\/|$)/)
  }

  test('编辑模块保存后重载仍然可见（持久化）', async ({ page }) => {
    await loginTeacher(page)
    await page.goto('/teacher/experiments')
    await expect(page.getByText('实验模块管理')).toBeVisible({ timeout: 15000 })

    // 编辑教师自己的 E2E 模块（兼容已改名/未改名的状态，保证可重复执行）
    const row = page.locator('tr', { hasText: /E2E 实验模块|E2E 测试实验/ }).first()
    await expect(row).toBeVisible({ timeout: 10000 })
    await row.getByRole('button', { name: '编辑模块' }).click()

    const nameInput = page.locator('input[name="module-name"]')
    await expect(nameInput).toBeVisible()
    await nameInput.fill('E2E 实验模块')
    await page.locator('[data-action="save-module"]').click()

    // 保存后列表刷新并显示新名称
    await expect(page.getByText('E2E 实验模块').first()).toBeVisible({ timeout: 10000 })

    // 重载后名称仍然存在（后端已持久化）
    await page.reload()
    await expect(page.getByText('E2E 实验模块').first()).toBeVisible({ timeout: 10000 })

    // 恢复原模块名，避免影响其他 e2e 流程对种子数据的依赖
    const renamedRow = page.locator('tr', { hasText: 'E2E 实验模块' }).first()
    await renamedRow.getByRole('button', { name: '编辑模块' }).click()
    await expect(nameInput).toBeVisible()
    await nameInput.fill('E2E 测试实验')
    await page.locator('[data-action="save-module"]').click()
    await expect(page.getByText('E2E 测试实验').first()).toBeVisible({ timeout: 10000 })
  })

  test('管理分页控件真实翻页', async ({ page }) => {
    await loginTeacher(page)
    await page.goto('/teacher/experiments')
    await expect(page.getByText('实验模块管理')).toBeVisible({ timeout: 15000 })

    // 数据量不足两页时跳过，避免 flaky
    const totalText = await page.locator('.pagination-bar > span').first().textContent()
    const total = parseInt((totalText || '').match(/\d+/)?.[0] || '0', 10)
    test.skip(total < 11, `实验模块共 ${total} 条，不足两页，跳过分页断言`)

    await page.locator('[aria-label="第 2 页"]').click()
    await expect(page.locator('[aria-label="第 2 页"]')).toHaveAttribute('aria-current', 'page')
    await expect(page.locator('tbody tr').first()).toBeVisible()
  })
})
