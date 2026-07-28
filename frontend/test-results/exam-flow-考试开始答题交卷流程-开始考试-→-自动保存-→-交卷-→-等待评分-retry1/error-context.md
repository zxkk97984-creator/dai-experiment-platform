# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: exam-flow.spec.js >> 考试开始答题交卷流程 >> 开始考试 → 自动保存 → 交卷 → 等待评分
- Location: e2e\exam-flow.spec.js:4:3

# Error details

```
Error: expect(page).toHaveURL(expected) failed

Expected pattern: /\/student\/exams/
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
  3  | test.describe('考试开始答题交卷流程', () => {
  4  |   test('开始考试 → 自动保存 → 交卷 → 等待评分', async ({ page }) => {
  5  |     // 学生登录
  6  |     await page.goto('/login')
  7  |     await expect(page.locator('#login-username')).toBeVisible()
  8  |     await page.fill('#login-username', 'student')
  9  |     await page.fill('#login-password', 'Passw0rd!')
  10 |     await page.click('button[type="submit"]')
  11 | 
  12 |     // 导航到考试列表
  13 |     await page.goto('/student/exams')
> 14 |     await expect(page).toHaveURL(/\/student\/exams/)
     |                        ^ Error: expect(page).toHaveURL(expected) failed
  15 | 
  16 |     // 点击第一个考试——必须存在
  17 |     const examLink = page.locator('a[href*="/student/exams/"]').first()
  18 |     await expect(examLink).toBeVisible({ timeout: 10000 })
  19 |     await examLink.click()
  20 | 
  21 |     // 点击开始考试——必须存在
  22 |     const startBtn = page.locator('button:has-text("开始考试")')
  23 |     await expect(startBtn).toBeVisible({ timeout: 10000 })
  24 |     await startBtn.click()
  25 | 
  26 |     // 等待题目加载——核心断言
  27 |     await expect(page.locator('.question-card, .exam-body')).toBeVisible({ timeout: 10000 })
  28 | 
  29 |     // 选择答案（如果有选项）
  30 |     const option = page.locator('.option-row').first()
  31 |     if (await option.isVisible({ timeout: 2000 }).catch(() => false)) {
  32 |       await option.click()
  33 |     }
  34 | 
  35 |     // 交卷——必须存在
  36 |     const submitBtn = page.locator('button:has-text("交卷")')
  37 |     await expect(submitBtn).toBeVisible({ timeout: 5000 })
  38 |     await submitBtn.click()
  39 |     await page.waitForTimeout(2000)
  40 |   })
  41 | })
  42 | 
```