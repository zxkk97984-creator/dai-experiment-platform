# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: experiment-flow.spec.js >> Notebook 实验提交评分流程 >> 学生运行 cell → 保存 → 提交 → 教师查看评分
- Location: e2e\experiment-flow.spec.js:4:3

# Error details

```
Error: expect(page).toHaveURL(expected) failed

Expected pattern: /\/student\/experiments/
Received string:  "http://localhost:8080/login"
Timeout: 5000ms

Call log:
  - Expect "toHaveURL" with timeout 5000ms
    14 × locator resolved to <html lang="zh-CN">…</html>
       - unexpected value "http://localhost:8080/login"

```

```yaml
- button "返回首页":
  - img
  - text: 返回首页
- img
- text: 人工智能 实验平台
- heading "欢迎回来" [level=1]
- paragraph: 登录你的学习账号，继续未完成的实验
- text: 用户名
- textbox "用户名":
  - /placeholder: 请输入用户名
- text: 密码
- textbox "密码":
  - /placeholder: 请输入密码
- button "显示密码":
  - img
- button "登 录":
  - text: 登 录
  - img
- paragraph:
  - text: 还没有账号？
  - link "返回首页了解平台":
    - /url: "#"
- contentinfo: © 2026 人工智能 实验平台 · Python Learning Studio
```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test'
  2  | 
  3  | test.describe('Notebook 实验提交评分流程', () => {
  4  |   test('学生运行 cell → 保存 → 提交 → 教师查看评分', async ({ page }) => {
  5  |     // 学生登录
  6  |     await page.goto('/login')
  7  |     await expect(page.locator('#login-username')).toBeVisible()
  8  |     await page.fill('#login-username', 'student')
  9  |     await page.fill('#login-password', 'Passw0rd!')
  10 |     await page.click('button[type="submit"]')
  11 | 
  12 |     // 导航到实验列表
  13 |     await page.goto('/student/experiments')
> 14 |     await expect(page).toHaveURL(/\/student\/experiments/)
     |                        ^ Error: expect(page).toHaveURL(expected) failed
  15 | 
  16 |     // 点击第一个实验——必须存在
  17 |     const expLink = page.locator('a[href*="/student/experiments/"]').first()
  18 |     await expect(expLink).toBeVisible({ timeout: 10000 })
  19 |     await expLink.click()
  20 | 
  21 |     // 执行代码 cell——必须有运行按钮
  22 |     const runBtn = page.locator('button:has-text("▶"), button:has-text("Run"), button[title="运行"]').first()
  23 |     await expect(runBtn).toBeVisible({ timeout: 10000 })
  24 |     await runBtn.click()
  25 |     // 等待执行完成
  26 |     await page.waitForTimeout(3000)
  27 | 
  28 |     // 打开菜单提交
  29 |     const menuBtn = page.locator('[aria-haspopup="menu"], .btn-icon').first()
  30 |     await expect(menuBtn).toBeVisible()
  31 |     await menuBtn.click()
  32 | 
  33 |     // 提交按钮必须存在
  34 |     const submitBtn = page.locator('.menu-submit, button:has-text("提交实验")')
  35 |     await expect(submitBtn).toBeVisible({ timeout: 5000 })
  36 |     await submitBtn.click()
  37 |     // 等待提交完成
  38 |     await page.waitForTimeout(2000)
  39 |   })
  40 | })
  41 | 
```