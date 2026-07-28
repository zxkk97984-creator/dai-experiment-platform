# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: course-flow.spec.js >> 课程学习主流程 >> 学生登录、选课、阅读课时
- Location: e2e\course-flow.spec.js:4:3

# Error details

```
Error: expect(page).toHaveURL(expected) failed

Expected pattern: /\/student\/courses/
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
- alert: 用户名或密码错误
- text: 用户名
- textbox "用户名":
  - /placeholder: 请输入用户名
  - text: student
- text: 密码
- textbox "密码":
  - /placeholder: 请输入密码
  - text: Passw0rd!
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
  3  | test.describe('课程学习主流程', () => {
  4  |   test('学生登录、选课、阅读课时', async ({ page }) => {
  5  |     // 学生登录
  6  |     await page.goto('/login')
  7  |     await expect(page.locator('#login-username')).toBeVisible()
  8  |     await page.fill('#login-username', 'student')
  9  |     await page.fill('#login-password', 'Passw0rd!')
  10 |     await page.click('button[type="submit"]')
  11 | 
  12 |     // 登录后应跳转到课程列表
> 13 |     await expect(page).toHaveURL(/\/student\/courses/)
     |                        ^ Error: expect(page).toHaveURL(expected) failed
  14 | 
  15 |     // 点击第一门课程——必须存在
  16 |     const courseCard = page.locator('.course-card, [data-test="course-item"]').first()
  17 |     await expect(courseCard).toBeVisible({ timeout: 10000 })
  18 |     await courseCard.click()
  19 | 
  20 |     // 应跳转到课程详情页
  21 |     await expect(page).toHaveURL(/\/student\/courses\/\d+/)
  22 |   })
  23 | })
  24 | 
```