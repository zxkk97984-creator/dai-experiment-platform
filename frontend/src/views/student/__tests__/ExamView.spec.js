// ExamView：review_required 学生提示 + started/grading/graded 行为回归
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '3' } }),
  onBeforeRouteLeave: (fn) => fn,
  createRouter: vi.fn(() => ({
    beforeEach: vi.fn(), afterEach: vi.fn(), beforeResolve: vi.fn(),
    push: vi.fn(), replace: vi.fn(),
    currentRoute: { value: { path: '/student/exams/3' } },
  })),
  createWebHistory: vi.fn(() => ({})),
}))

vi.mock('../../../api/exams.js', () => ({
  examsAPI: {
    get: vi.fn(),
    getQuestions: vi.fn(),
    getMyGrade: vi.fn(),
    saveAnswer: vi.fn(),
    submit: vi.fn(),
    start: vi.fn(),
  },
}))

vi.mock('../../../stores/app.js', () => ({
  useAppStore: () => ({ showToast: vi.fn() }),
}))

import { examsAPI } from '../../../api/exams.js'

const EXAM = { id: 3, title: '期中考试', duration_minutes: 60, total_points: 30 }
const QUESTIONS = {
  data: {
    items: [
      { id: 1, question_type: 'single_choice', points: 10 },
      { id: 2, question_type: 'code', points: 20 },
    ],
  },
}

async function mountExam(status, extra = {}) {
  examsAPI.get.mockResolvedValue({ data: EXAM })
  examsAPI.getQuestions.mockResolvedValue(QUESTIONS)
  examsAPI.getMyGrade.mockResolvedValue({
    data: { submission_id: 7, status, score: null, answers: [], ...extra },
  })
  const mod = await import('../ExamView.vue')
  const wrapper = mount(mod.default, {
    global: {
      stubs: {
        AppLayout: { template: '<div><slot /></div>' },
        StudentAIGradingResult: { template: '<div class="ai-result-stub" />' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('ExamView 状态展示', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('review_required：显示人工处理提示，不显示"等待评分"', async () => {
    const wrapper = await mountExam('review_required')
    const text = wrapper.text()
    expect(text).toContain('评分遇到系统问题，已转人工处理，不会按 0 分计入')
    expect(text).not.toContain('已交卷，等待评分')
    // 不泄露内部信息
    expect(text).not.toContain('system_error')
    expect(text).not.toContain('hidden')
  })

  it('graded：显示最终得分（回归）', async () => {
    const wrapper = await mountExam('graded', { score: 25 })
    expect(wrapper.text()).toContain('已评分：25 分')
  })

  it('grading：仍显示"已交卷，等待评分"（回归）', async () => {
    const wrapper = await mountExam('grading')
    expect(wrapper.text()).toContain('已交卷，等待评分')
  })

  it('started：无提交记录时不显示评分提示，出现考试主体（回归）', async () => {
    const wrapper = await mountExam('started', {
      expires_at: new Date(Date.now() + 600000).toISOString(),
    })
    expect(wrapper.text()).not.toContain('已交卷')
    expect(wrapper.text()).not.toContain('评分遇到系统问题')
    expect(wrapper.find('.exam-body').exists()).toBe(true)
  })
})
