/** 教师 AI 评分复核：列表 + 详情（评分工作台）测试 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const { mockedAuth } = vi.hoisted(() => ({
  mockedAuth: {
    isAdmin: false,
    isTeacher: true,
    isStudent: false,
    user: { id: 1, username: 'teacher', role: 'teacher' },
  },
}))

vi.mock('../../../api/aiGrading.js', () => ({
  aiGradingAPI: {
    listGrades: vi.fn(),
    getGrade: vi.fn(),
    retryGrade: vi.fn(),
    overrideGrade: vi.fn(),
  },
}))

vi.mock('../../../stores/auth.js', () => ({
  useAuthStore: () => mockedAuth,
}))

const routeQuery = {}
const { routerPush } = vi.hoisted(() => ({ routerPush: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '7' }, query: routeQuery, path: '/teacher/ai-grading/7' }),
  useRouter: () => ({ push: routerPush, replace: vi.fn() }),
  createRouter: vi.fn(() => ({
    beforeResolve: vi.fn(), push: vi.fn(), replace: vi.fn(),
    currentRoute: { value: { path: '/teacher/ai-grading' } },
  })),
  createWebHistory: vi.fn(() => ({})),
}))

import { aiGradingAPI } from '../../../api/aiGrading.js'

// ── 列表测试（保持既有断言语义） ─────────────────────────────────

describe('AI 评分复核列表', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    Object.assign(mockedAuth, {
      isAdmin: false,
      isTeacher: true,
      isStudent: false,
      user: { id: 1, username: 'teacher', role: 'teacher' },
    })
  })

  it('加载并展示评分列表', async () => {
    aiGradingAPI.listGrades.mockResolvedValue({
      data: {
        items: [
          { id: 1, submission_id: 5, mode: 'shadow', status: 'completed',
            functional_score: 54, algorithm_score: 13, robustness_score: 7, quality_score: 5,
            raw_total: 79, score_cap: null, final_score_100: 79, needs_teacher_review: false,
            attempt_count: 1, created_at: '2026-01-01T00:00:00' },
        ],
        total: 1, page: 1, page_size: 20,
      },
    })

    const mod = await import('../AIGradingReviewView.vue')
    const wrapper = mount(mod.default, {
      global: { stubs: { 'router-link': { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    expect(aiGradingAPI.listGrades).toHaveBeenCalled()
    const text = wrapper.text()
    expect(text).toContain('79')
    expect(text).toContain('影子评分')
    expect(text).toContain('全部评分')
    expect(text).toContain('已完成')
  })

  it('按学生姓名查询并显示学生信息', async () => {
    aiGradingAPI.listGrades.mockResolvedValue({
      data: {
        items: [
          { id: 3, submission_id: 8, student_id: 42, student_name: '张三', mode: 'active', status: 'completed',
            functional_score: 60, algorithm_score: 20, robustness_score: 10, quality_score: 10,
            raw_total: 100, score_cap: null, final_score_100: 100, needs_teacher_review: false,
            attempt_count: 1, created_at: '2026-01-03T00:00:00' },
        ],
        total: 1, page: 1, page_size: 20,
      },
    })

    const mod = await import('../AIGradingReviewView.vue')
    const wrapper = mount(mod.default, {
      global: { stubs: { 'router-link': { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    await wrapper.find('input').setValue('张三')
    await wrapper.find('.filter-bar').trigger('submit')
    await flushPromises()

    expect(aiGradingAPI.listGrades).toHaveBeenCalledWith(expect.objectContaining({ student_name: '张三' }))
    expect(wrapper.text()).toContain('学生 ID')
    expect(wrapper.text()).toContain('学生信息')
    expect(wrapper.text()).toContain('42')
    expect(wrapper.text()).toContain('张三')
  })

  it('状态 badge 正确映射', async () => {
    aiGradingAPI.listGrades.mockResolvedValue({
      data: {
        items: [
          { id: 2, submission_id: 6, mode: 'active', status: 'review_required',
            functional_score: 60, algorithm_score: null, robustness_score: 10, quality_score: null,
            raw_total: null, score_cap: null, final_score_100: null, needs_teacher_review: true,
            attempt_count: 3, created_at: '2026-01-02T00:00:00' },
        ],
        total: 1, page: 1, page_size: 20,
      },
    })

    const mod = await import('../AIGradingReviewView.vue')
    const wrapper = mount(mod.default, {
      global: { stubs: { 'router-link': { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('需复核')
    expect(text).toContain('复核状态')
  })

  it('管理员列表使用管理员详情路由', async () => {
    Object.assign(mockedAuth, {
      isAdmin: true,
      isTeacher: false,
      user: { id: 2, username: 'admin', role: 'admin' },
    })
    aiGradingAPI.listGrades.mockResolvedValue({
      data: {
        items: [{
          id: 9, submission_id: 5, student_id: 17, student_name: '爱丽丝',
          mode: 'active', status: 'completed', functional_score: 60,
          algorithm_score: 20, robustness_score: 10, quality_score: 10,
          raw_total: 100, score_cap: null, final_score_100: 100,
          needs_teacher_review: false, created_at: '2026-01-03T00:00:00',
        }],
        total: 1, page: 1, page_size: 10,
      },
    })

    const mod = await import('../AIGradingReviewView.vue')
    const wrapper = mount(mod.default, {
      global: {
        stubs: {
          'router-link': {
            props: ['to'],
            template: '<a :href="to"><slot /></a>',
          },
        },
      },
    })
    await flushPromises()

    expect(wrapper.get('.row-action').attributes('href')).toBe('/admin/ai-grading/9')
  })
})

// ── 详情（评分工作台）测试 ───────────────────────────────────────

const DETAIL_FIXTURE = {
  id: 7, submission_id: 5, rubric_id: 3, mode: 'active', status: 'review_required',
  functional_score: 54, algorithm_score: 13, robustness_score: 7, quality_score: 5,
  raw_total: 79, score_cap: null, final_score_100: 79, scaled_score: 79,
  student_name: '李同学', student_username: 'student_alice',
  question_title: '有效括号', course_title: 'Python 编程与算法实践',
  submitted_at: '2026-08-02T11:32:00', finished_at: '2026-08-02T11:35:00',
  execution_time_ms: 42,
  student_code: 'def is_valid(s):\n    return True\n',
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
  static_analysis: { parse_error: null, metrics: { lines: 12, functions: 2, complexity: 3 }, diagnostics: [] },
  ai_result: {
    rubric_version: 3,
    algorithm: {
      dimension_score: 13, dimension_max: 20,
      items: [{ criterion_id: 'A1', criterion: '搜索区间', level: 'complete',
                score: 10, max_score: 10, code_lines: [1, 2], evidence: '正确检查了栈顶' }],
    },
    code_quality: { dimension_score: 5, dimension_max: 10, items: [] },
    student_feedback: { strengths: ['结构清晰'], issues: [], suggestions: ['补充类型注解'] },
  },
  raw_response: '{"algorithm":{...}}',
  overrides: [],
}

async function mountDetail(fixture = DETAIL_FIXTURE) {
  aiGradingAPI.getGrade.mockResolvedValue({ data: fixture })
  const mod = await import('../AIGradingReviewDetailView.vue')
  const wrapper = mount(mod.default, {
    global: {
      stubs: {
        'router-link': { template: '<a><slot /></a>' },
        CodeViewer: {
          props: ['code', 'highlightLines', 'activeLine'],
          template: '<div class="cv-stub" :data-active="activeLine">{{ code }}</div>',
        },
        TeacherReviewPanel: { template: '<div class="review-panel-stub" />' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('AI 评分详情（评分工作台）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    Object.keys(routeQuery).forEach((k) => delete routeQuery[k])
    Object.assign(mockedAuth, {
      isAdmin: false,
      isTeacher: true,
      isStudent: false,
      user: { id: 1, username: 'teacher', role: 'teacher' },
    })
  })

  it('标题含作业标题，编号为辅助信息', async () => {
    const wrapper = await mountDetail()
    expect(wrapper.text()).toContain('有效括号')
    expect(wrapper.text()).toContain('#7')
    expect(aiGradingAPI.getGrade).toHaveBeenCalledWith('7')
  })

  it('展示学生、课程、提交时间上下文', async () => {
    const wrapper = await mountDetail()
    const text = wrapper.text()
    expect(text).toContain('李同学')
    expect(text).toContain('student_alice')
    expect(text).toContain('Python 编程与算法实践')
    expect(text).toContain('提交时间')
  })

  it('状态徽章：review_required 显示等待教师复核', async () => {
    const wrapper = await mountDetail()
    expect(wrapper.text()).toContain('等待教师复核')
  })

  it('测试摘要：通过数/总数与运行时间', async () => {
    const wrapper = await mountDetail()
    const text = wrapper.text()
    expect(text).toContain('11 / 12') // 8+3 通过 / 8+1+0+3+0+0 总
    expect(text).toContain('42')
  })

  it('测试组表格与系统错误（不重复计入摘要）', async () => {
    const wrapper = await mountDetail({ ...DETAIL_FIXTURE, deterministic_details: {
      groups: [{ id: 'F1', name: '基础用例', dimension: 'F', max_score: 40, score: 0,
                 counts: { passed: 0, failed: 1, errors: 0 } }],
      system_errors: ['测试组 F1 执行异常'],
    } })
    expect(wrapper.text()).toContain('基础用例')
    expect(wrapper.text()).toContain('失败 1')
    expect(wrapper.text()).toContain('测试组 F1 执行异常')
    expect(wrapper.text()).toContain('0 / 1') // 摘要 total 不含系统错误
  })

  it('AI 评分依据条目与行号引用', async () => {
    const wrapper = await mountDetail()
    expect(wrapper.text()).toContain('搜索区间')
    expect(wrapper.text()).toContain('正确检查了栈顶')
    // 每行一个定位按钮
    expect(wrapper.findAll('.evidence-lines .line-chip')).toHaveLength(2)
    expect(wrapper.find('.evidence-lines .line-chip').text()).toContain('第 1 行')
  })

  it('点击行号更新 CodeViewer activeLine', async () => {
    const wrapper = await mountDetail()
    await wrapper.findAll('.evidence-lines button').find((b) => b.text().includes('1')).trigger('click')
    await flushPromises()
    expect(wrapper.find('.cv-stub').attributes('data-active')).toBe('1')
  })

  it('学生反馈三区块', async () => {
    const wrapper = await mountDetail()
    const text = wrapper.text()
    expect(text).toContain('做得较好的部分')
    expect(text).toContain('结构清晰')
    expect(text).toContain('需要改进')
    expect(text).toContain('本次提交未发现需要修改的核心问题。')
    expect(text).toContain('后续建议')
  })

  it('高级信息默认折叠：原始 JSON 与技术字段', async () => {
    const wrapper = await mountDetail()
    const advanced = wrapper.find('.advanced-info')
    expect(advanced.exists()).toBe(true)
    expect(advanced.attributes('open')).toBeUndefined()
    expect(advanced.text()).toContain('AI 原始响应')
    expect(advanced.text()).toContain('评分尝试')
    expect(advanced.text()).toContain('1 次')
    expect(advanced.text()).toContain('评分规则版本 3')
  })

  it('静态分析摘要展示', async () => {
    const wrapper = await mountDetail()
    expect(wrapper.text()).toContain('12 行')
    expect(wrapper.text()).toContain('圈复杂度 3')
  })

  it('无上下文字段时回退"提交 #id"', async () => {
    const wrapper = await mountDetail({
      ...DETAIL_FIXTURE, question_title: null, course_title: null, student_name: null,
      student_username: null, submitted_at: null,
    })
    expect(wrapper.text()).toContain('提交 #7')
  })

  it('加载中与错误状态', async () => {
    aiGradingAPI.getGrade.mockRejectedValueOnce({ response: { data: { detail: { message: '加载失败' } } } })
    const mod = await import('../AIGradingReviewDetailView.vue')
    const wrapper = mount(mod.default, {
      global: { stubs: { CodeViewer: { template: '<div />' }, TeacherReviewPanel: { template: '<div />' } } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('加载失败')
  })

  it('返回列表按钮回传筛选上下文', async () => {
    routeQuery.kind = 'assignment'
    routeQuery.status = 'review_required'
    routeQuery.page = '2'
    const wrapper = await mountDetail()
    await wrapper.findAll('button').find((b) => b.text().includes('返回')).trigger('click')
    await flushPromises()
    expect(routerPush).toHaveBeenCalledWith({
      path: '/teacher/ai-grading',
      query: { kind: 'assignment', status: 'review_required', page: '2' },
    })
  })
})
