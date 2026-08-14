// 教师 AI 评分详情（评分工作台）E2E：
// 1. 列表烟雾：真实列表页零 404/500/console error（数据无关）
// 2. 详情确定性：route 拦截详情接口返回固定 fixture，
//    断言上下文/最终得分/F·A·R·Q/测试摘要/高级信息折叠/确认弹窗/无横向溢出
import { test, expect } from '@playwright/test'
import { TEACHER_USER, TEACHER_PASS } from './credentials.js'

const LIST_ITEM = {
  id: 7, submission_id: 5, mode: 'active', status: 'review_required',
  functional_score: 54, algorithm_score: 13, robustness_score: 7, quality_score: 5,
  raw_total: 79, score_cap: null, final_score_100: 79,
  needs_teacher_review: true, attempt_count: 1, created_at: '2026-08-02T11:32:00',
}

const DETAIL_FIXTURE = {
  id: 7, submission_id: 5, rubric_id: 3, mode: 'active', status: 'review_required',
  functional_score: 54, algorithm_score: 13, robustness_score: 7, quality_score: 5,
  raw_total: 79, score_cap: null, final_score_100: 79, scaled_score: 79,
  student_name: '李同学', student_username: 'student_24621600_01',
  question_title: '有效括号', course_title: 'Python 编程与算法实践',
  submitted_at: '2026-08-02T11:32:00', finished_at: '2026-08-02T11:35:00',
  execution_time_ms: 42,
  student_code: 'def is_valid(s):\n    stack = []\n    return not stack\n',
  needs_teacher_review: true, review_reason: '测试警告',
  attempt_count: 1, last_error: null,
  deterministic_details: {
    groups: [
      { id: 'F1', name: '基础用例', dimension: 'F', max_score: 40, score: 34,
        counts: { passed: 8, failed: 1, errors: 0 } },
      { id: 'R1', name: '性能', dimension: 'R', max_score: 10, score: 7,
        counts: { passed: 3, failed: 0, errors: 0 } },
    ],
    system_errors: [],
  },
  static_analysis: { parse_error: null, metrics: { lines: 3, functions: 1, complexity: 1 }, diagnostics: [] },
  ai_result: {
    rubric_version: 3,
    algorithm: {
      dimension_score: 13, dimension_max: 20,
      items: [{ criterion_id: 'A1', criterion: '搜索区间', level: 'complete',
                score: 10, max_score: 10, code_lines: [1, 2], evidence: '正确检查了栈顶' }],
    },
    code_quality: { dimension_score: 5, dimension_max: 10, items: [] },
    student_feedback: { strengths: ['结构清晰'], issues: [], suggestions: [] },
  },
  raw_response: '{"algorithm":{"dimension_score":13}}',
  overrides: [],
}

test.describe('教师 AI 评分列表与详情', () => {
  test('列表烟雾：真实列表零 404/500/console error', async ({ page }) => {
    const errors = []
    page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`))
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(`console: ${msg.text()}`)
    })
    page.on('response', (res) => {
      if (res.status() >= 400) errors.push(`http ${res.status()}: ${res.url()}`)
    })

    await page.goto('/login')
    await page.fill('#login-username', TEACHER_USER)
    await page.fill('#login-password', TEACHER_PASS)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/teacher$/, { timeout: 15000 })

    await page.goto('/teacher/ai-grading')
    // 列表页本身可用（有数据 .grade-table，或空态 .state-panel，或加载骨架均可）
    await expect(page.locator('.grade-table, .table-skeleton, .state-panel').first()).toBeVisible({ timeout: 15000 })

    expect(errors).toEqual([])
  })

  test('详情页：上下文、最终得分、F/A/R/Q、测试摘要、高级信息折叠、确认弹窗、无溢出', async ({ page }) => {
    const errors = []
    page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`))
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(`console: ${msg.text()}`)
    })

    // 拦截列表与详情（确定性数据，不依赖真实库）。
    // 列表请求带 query（page/page_size），glob `.../grades` 匹配不到完整 URL，
    // 用 pathname 精确匹配；详情/复核用 `grades/**` 通配。
    await page.route((url) => url.pathname === '/api/v1/ai-grading/grades', (route) => {
      route.fulfill({ json: { items: [LIST_ITEM], total: 1, page: 1, page_size: 20 } })
    })
    await page.route('**/api/v1/ai-grading/grades/**', (route) => {
      const req = route.request()
      if (req.method() === 'POST') {
        route.fulfill({ json: { ok: true } })
      } else {
        route.fulfill({ json: DETAIL_FIXTURE })
      }
    })

    await page.goto('/login')
    await page.fill('#login-username', TEACHER_USER)
    await page.fill('#login-password', TEACHER_PASS)
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(/\/teacher$/, { timeout: 15000 })

    // 从列表进入详情
    await page.goto('/teacher/ai-grading')
    await page.locator('.grade-table a').first().click()
    await expect(page).toHaveURL(/\/teacher\/ai-grading\/\d+$/)

    // 上下文与标题
    await expect(page.locator('.grading-title')).toContainText('有效括号')
    await expect(page.locator('.grading-context')).toContainText('李同学')
    await expect(page.locator('.grading-context')).toContainText('student_24621600_01')
    await expect(page.locator('.grading-context')).toContainText('Python 编程与算法实践')

    // 最终得分与 F/A/R/Q
    await expect(page.locator('.score-overview__value')).toHaveText('79')
    await expect(page.locator('.score-overview')).toContainText('功能正确性')
    await expect(page.locator('.score-overview')).toContainText('算法关键步骤')
    await expect(page.locator('.score-overview')).toContainText('鲁棒性与性能')
    await expect(page.locator('.score-overview')).toContainText('代码质量')

    // 测试摘要
    await expect(page.locator('.grading-summary-line')).toContainText('11 / 12')
    await expect(page.locator('.grading-summary-line')).toContainText('42')

    // 高级信息默认折叠：summary 可见、body 隐藏
    const advanced = page.locator('.advanced-info')
    await expect(advanced).toBeVisible()
    await expect(advanced.locator('.advanced-info__body')).toBeHidden()
    await advanced.locator('summary').click()
    await expect(advanced.locator('.advanced-info__body')).toBeVisible()
    await expect(advanced).toContainText('AI 原始响应')

    // 确认弹窗：修改 A + 理由 → 弹窗出现 → 取消
    await page.fill('#ov-a', '10')
    await page.fill('#ov-reason', '教师复核调整说明')
    await page.locator('.review-submit').click()
    await expect(page.locator('.confirm-dialog')).toBeVisible()
    await expect(page.locator('.confirm-dialog')).toContainText('算法关键步骤 13 → 10')
    await page.locator('.confirm-dialog button', { hasText: '取消' }).click()
    await expect(page.locator('.confirm-dialog')).toHaveCount(0)

    // 无横向溢出
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
    expect(overflow).toBe(false)

    expect(errors).toEqual([])
  })
})
