import { test, expect } from '@playwright/test'

test.describe('教师调整作业截止时间完整流程', () => {
  test('已截止作业延长后学生聚焦恢复，再设为过去后重新禁用', async ({ browser }) => {
    let dueAt = '2020-01-01T00:00:00.000Z'
    const publishedAt = '2026-08-01T01:00:00.000Z'

    const assignment = () => ({
      id: 1,
      course_id: 1,
      course_title: 'Python 作业时间验收课',
      title: '截止时间联动验收作业',
      description: '验证教师调整后学生端即时恢复与关闭',
      status: 'published',
      published_at: publishedAt,
      due_at: dueAt,
      created_at: publishedAt,
      updated_at: publishedAt,
      environment_summary: null,
    })

    async function installApiMocks(page) {
      let signedInUser = null
      await page.route('**/api/v1/**', async (route) => {
        const request = route.request()
        const url = new URL(request.url())
        const path = url.pathname
        const method = request.method()
        const json = (body, status = 200) => route.fulfill({
          status,
          contentType: 'application/json',
          body: JSON.stringify(body),
        })

        if (path === '/api/v1/auth/login' && method === 'POST') {
          const payload = request.postDataJSON()
          const teacher = payload.username === 'qa_teacher'
          signedInUser = {
            id: teacher ? 1 : 2,
            username: payload.username,
            real_name: teacher ? '验收教师' : '验收学生',
            role: teacher ? 'teacher' : 'student',
            status: 'active',
          }
          return json({ access_token: `mock-${signedInUser.role}`, user: signedInUser })
        }
        if (path === '/api/v1/auth/logout' && method === 'POST') {
          signedInUser = null
          return route.fulfill({ status: 204, body: '' })
        }
        if (path === '/api/v1/auth/refresh') {
          return signedInUser
            ? json({ access_token: `mock-${signedInUser.role}`, user: signedInUser })
            : json({ detail: { code: 'NO_REFRESH_TOKEN' } }, 401)
        }
        if (path === '/api/v1/auth/me') return signedInUser ? json(signedInUser) : json({}, 401)

        if (path === '/api/v1/assignments/1/questions') {
          return json({
            items: [{
              id: 10,
              assignment_id: 1,
              title: '正数求和',
              description: '返回所有正数之和',
              function_name: 'sum_positive',
              starter_code: 'def sum_positive(values):\n    pass',
              public_cases: [],
              grading_mode: 'legacy',
              environment_summary: null,
            }],
          })
        }
        if (path === '/api/v1/assignments/1' && method === 'PATCH') {
          dueAt = request.postDataJSON().due_at
          return json(assignment())
        }
        if (path === '/api/v1/assignments/1') return json(assignment())
        if (path === '/api/v1/assignments') {
          return json({ items: [assignment()], total: 1, page: 1, page_size: 100 })
        }
        if (path === '/api/v1/courses') {
          return json({ items: [{ id: 1, title: 'Python 作业时间验收课', teaching_classes: [] }], total: 1 })
        }
        if (path === '/api/v1/judge/submissions') return json({ items: [] })

        return json({ items: [] })
      })
    }

    async function login(page, username, target) {
      await page.goto('/login')
      await page.locator('#login-username').fill(username)
      await page.locator('#login-password').fill('mock-password')
      await page.locator('button[type="submit"]').click()
      await expect(page).toHaveURL(new RegExp(`${target}$`))
    }

    const teacherContext = await browser.newContext({ viewport: { width: 1600, height: 900 } })
    const studentContext = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    const teacherPage = await teacherContext.newPage()
    const studentPage = await studentContext.newPage()
    await installApiMocks(teacherPage)
    await installApiMocks(studentPage)

    await login(studentPage, 'qa_student', '/student')
    await studentPage.goto('/student/assignments/1')
    await expect(studentPage.getByText('作业已截止', { exact: true })).toBeVisible()
    await expect(studentPage.locator('.btn-self-test')).toBeDisabled()
    await expect(studentPage.locator('.btn-submit-code')).toBeDisabled()

    await login(teacherPage, 'qa_teacher', '/teacher')
    await teacherPage.goto('/teacher/assignments')
    await expect(teacherPage.getByRole('columnheader', { name: '时间安排' })).toBeVisible()
    await expect(teacherPage.getByText('已截止', { exact: true }).first()).toBeVisible()
    await teacherPage.getByRole('button', { name: '调整截止' }).click()
    await expect(teacherPage.getByText('首次发布时间', { exact: true })).toBeVisible()
    await teacherPage.locator('#schedule-due-at').fill('2099-12-31T23:59')
    await teacherPage.getByRole('button', { name: '保存时间设置' }).click()
    await expect(teacherPage.getByText('截止时间已更新', { exact: true })).toBeVisible()

    await studentPage.bringToFront()
    await studentPage.evaluate(() => window.dispatchEvent(new Event('focus')))
    await expect(studentPage.getByText('作业进行中', { exact: true })).toBeVisible()
    await expect(studentPage.locator('.btn-self-test')).toBeEnabled()
    await expect(studentPage.locator('.btn-submit-code')).toBeEnabled()

    await teacherPage.bringToFront()
    await teacherPage.getByRole('button', { name: '调整截止' }).click()
    await teacherPage.locator('#schedule-due-at').fill('2020-01-01T00:00')
    await teacherPage.getByRole('button', { name: '保存时间设置' }).click()
    await expect(teacherPage.getByText('学生将立即无法运行或提交')).toBeVisible()
    await teacherPage.getByRole('button', { name: '确认保存' }).click()
    await expect(teacherPage.getByText('截止时间已更新', { exact: true })).toBeVisible()

    await studentPage.bringToFront()
    await studentPage.evaluate(() => window.dispatchEvent(new Event('focus')))
    await expect(studentPage.getByText('作业已截止', { exact: true })).toBeVisible()
    await expect(studentPage.locator('.btn-self-test')).toBeDisabled()
    await expect(studentPage.locator('.btn-submit-code')).toBeDisabled()

    await studentPage.setViewportSize({ width: 390, height: 844 })
    await expect(studentPage.locator('.deadline-banner')).toBeVisible()
    await expect(studentPage.locator('.btn-submit-code')).toBeVisible()
    const hasHorizontalOverflow = await studentPage.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    )
    expect(hasHorizontalOverflow).toBe(false)

    await teacherContext.close()
    await studentContext.close()
  })
})
