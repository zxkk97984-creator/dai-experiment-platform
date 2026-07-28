# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: assignment-flow.spec.js >> 作业提交判题流程 >> 学生提交代码 → Worker 判题 → 查看结果
- Location: e2e\assignment-flow.spec.js:4:3

# Error details

```
Error: expect(page).toHaveURL(expected) failed

Expected pattern: /\/student\/assignments/
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
  3  | test.describe('作业提交判题流程', () => {
  4  |   test('学生提交代码 → Worker 判题 → 查看结果', async ({ page }) => {
  5  |     // 学生登录
  6  |     await page.goto('/login')
  7  |     await expect(page.locator('#login-username')).toBeVisible()
  8  |     await page.fill('#login-username', 'student')
  9  |     await page.fill('#login-password', 'Passw0rd!')
  10 |     await page.click('button[type="submit"]')
  11 | 
  12 |     // 导航到作业列表
  13 |     await page.goto('/student/assignments')
> 14 |     await expect(page).toHaveURL(/\/student\/assignments/)
     |                        ^ Error: expect(page).toHaveURL(expected) failed
  15 | 
  16 |     // 点击第一个作业——必须存在
  17 |     const assignmentLink = page.locator('a[href*="/student/assignments/"]').first()
  18 |     await expect(assignmentLink).toBeVisible({ timeout: 10000 })
  19 |     await assignmentLink.click()
  20 | 
  21 |     // 代码编辑器——必须存在
  22 |     const editor = page.locator('textarea, .code-editor, [contenteditable]').first()
  23 |     await expect(editor).toBeVisible({ timeout: 10000 })
  24 |     await editor.fill('def add(a, b):\n    return a + b')
  25 | 
  26 |     // 提交按钮——必须存在
  27 |     const submitBtn = page.locator('button:has-text("提交")')
  28 |     await expect(submitBtn).toBeVisible()
  29 |     await submitBtn.click()
  30 | 
  31 |     // 等待判题结果——核心断言（匹配任一判题结果状态文本）
  32 |     await expect(page.getByText(/accepted|wrong_answer|runtime_error|time_limit/)).toBeVisible({ timeout: 30000 })
  33 |   })
  34 | })
  35 | 
```