import { expect, test } from '@playwright/test'

const serverNow = '2026-08-14T10:00:00Z'
const questions = [
  { id: 1, question_type: 'single_choice', prompt: '第一题', options: { A: 'A', B: 'B' }, points: 5 },
  { id: 2, question_type: 'single_choice', prompt: '第二题', options: { A: 'A', B: 'B' }, points: 5 },
  { id: 3, question_type: 'single_choice', prompt: '第三题', options: { A: 'A', B: 'B' }, points: 5 },
  { id: 4, question_type: 'single_choice', prompt: '第四题', options: { A: 'A', B: 'B' }, points: 5 },
  { id: 5, question_type: 'code', prompt: '实现 add(a, b)', starter_code: 'def add(a, b):\n    return a + b', public_cases: [{ args: [1, 2], expected: 3 }], points: 10 },
  { id: 6, question_type: 'fill_blank', prompt: '结果是 [[blank:value]]', points: 5 },
]

test('进行中考试倒计时、题号布局、编程题自测和未完成确认保持一致', async ({ page }) => {
  await page.route('**/api/v1/auth/refresh', route => route.fulfill({
    json: { access_token: 'browser-test-token', user: { id: 9, username: 'student', real_name: '验收学生', role: 'student' } },
  }))
  await page.route('**/api/v1/exams/4/session', route => route.fulfill({
    json: {
      server_now: serverNow,
      expires_at: '2026-08-14T10:30:00Z',
      exam: { id: 4, title: '验收考试', duration_minutes: 30, max_score: 35, student_status: 'in_progress' },
      submission: { id: 19, status: 'started', expires_at: null, score: null, score_visible: false },
      questions,
      saved_answers: [],
      visibility: {},
    },
  }))
  await page.route('**/api/v1/exams/4/answers', async route => {
    const body = route.request().postDataJSON()
    await route.fulfill({
      json: {
        server_now: serverNow,
        results: body.answers.map(answer => ({ question_id: answer.question_id, ok: true, version: 1 })),
      },
    })
  })
  await page.route('**/api/v1/exams/4/questions/5/sample-run', route => route.fulfill({
    json: { status: 'accepted', output: '1 passed', execution_time_ms: 12 },
  }))

  await page.goto('/student/exams/4')
  await expect(page.getByRole('heading', { name: '验收考试' })).toBeVisible()
  await expect(page.locator('.timer strong')).toHaveText(/00:29:(5\d|4\d)/)

  const sidebarBox = await page.locator('.exam-sidebar').boundingBox()
  const navBoxes = await page.locator('.exam-sidebar nav button').evaluateAll(buttons => buttons.map(button => {
    const rect = button.getBoundingClientRect()
    return { left: rect.left, right: rect.right }
  }))
  expect(sidebarBox).not.toBeNull()
  for (const box of navBoxes) {
    expect(box.left).toBeGreaterThanOrEqual(sidebarBox.x)
    expect(box.right).toBeLessThanOrEqual(sidebarBox.x + sidebarBox.width)
  }

  const codeNav = page.locator('.exam-sidebar nav button').nth(4)
  await expect(codeNav).not.toHaveClass(/answered/)
  await page.getByRole('button', { name: '运行自测' }).click()
  await expect(page.getByText('公开样例全部通过')).toBeVisible()
  await expect(codeNav).toHaveClass(/answered/)

  await page.getByRole('button', { name: /返回考试中心/ }).click()
  await expect(page.getByText('当前尚有未完成的题目，退出将暂存题目')).toBeVisible()
  await expect(page.getByRole('button', { name: '确定' })).toBeVisible()
  await page.getByRole('button', { name: '取消' }).click()
  await expect(page).toHaveURL(/\/student\/exams\/4$/)

  await page.getByRole('button', { name: '提交试卷' }).click()
  await expect(page.getByText('当前尚有未完成的题目，确定交卷吗')).toBeVisible()
  await expect(page.getByRole('button', { name: '确定' })).toBeVisible()
  await expect(page.getByRole('button', { name: '取消' })).toBeVisible()
})
