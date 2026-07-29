/** Task 12: 教师复核列表与详情——真实组件挂载测试 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../../api/aiGrading.js', () => ({
  aiGradingAPI: {
    listGrades: vi.fn(),
    getGrade: vi.fn(),
    retryGrade: vi.fn(),
    overrideGrade: vi.fn(),
  },
}))

vi.mock('../../../stores/auth.js', () => ({
  useAuthStore: () => ({
    isAdmin: false,
    isTeacher: true,
    isStudent: false,
    user: { id: 1, username: 'teacher', role: 'teacher' },
  }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' }, path: '/teacher/ai-grading' }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  createRouter: vi.fn(() => ({
    beforeResolve: vi.fn(), push: vi.fn(), replace: vi.fn(),
    currentRoute: { value: { path: '/teacher/ai-grading' } },
  })),
  createWebHistory: vi.fn(() => ({})),
}))

import { aiGradingAPI } from '../../../api/aiGrading.js'

describe('AI 评分复核列表', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
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
      global: {
        stubs: { 'router-link': { template: '<a><slot /></a>' } },
      },
    })
    await flushPromises()

    expect(aiGradingAPI.listGrades).toHaveBeenCalled()
    const text = wrapper.text()
    expect(text).toContain('79')
    expect(text).toContain('shadow')
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
      global: {
        stubs: { 'router-link': { template: '<a><slot /></a>' } },
      },
    })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('需复核')
    expect(text).toContain('是')
  })
})

describe('AI 评分详情', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('展示分项评分详情', async () => {
    aiGradingAPI.getGrade.mockResolvedValue({
      data: {
        id: 1, submission_id: 5, rubric_id: 1, mode: 'active', status: 'completed',
        functional_score: 54, algorithm_score: 13, robustness_score: 7, quality_score: 5,
        raw_total: 79, score_cap: null, final_score_100: 79, scaled_score: 79,
        ai_result: {
          algorithm: {
            dimension_score: 13, dimension_max: 20,
            items: [{ criterion_id: 'A1', criterion: '搜索区间', level: 'complete', score: 10, max_score: 10, code_lines: [1, 2], evidence: '正确' }],
          },
          code_quality: { dimension_score: 5, dimension_max: 10, items: [] },
          student_feedback: { strengths: [], issues: [], suggestions: [] },
        },
        overrides: [],
        raw_response: '{"algorithm":{...}}',
      },
    })

    const mod = await import('../AIGradingReviewDetailView.vue')
    const wrapper = mount(mod.default, {
      global: {
        stubs: { 'router-link': { template: '<a><slot /></a>' } },
      },
    })
    await flushPromises()

    expect(aiGradingAPI.getGrade).toHaveBeenCalledWith('1')
    const text = wrapper.text()
    expect(text).toContain('79')
    expect(text).toContain('搜索区间')
  })

  it('覆盖操作需要理由', async () => {
    aiGradingAPI.getGrade.mockResolvedValue({
      data: {
        id: 3, submission_id: 7, rubric_id: 1, mode: 'active', status: 'review_required',
        functional_score: 50, algorithm_score: 10, robustness_score: 5, quality_score: 3,
        raw_total: 68, score_cap: null, final_score_100: 68, scaled_score: 68,
        ai_result: null, overrides: [],
      },
    })

    const mod = await import('../AIGradingReviewDetailView.vue')
    const wrapper = mount(mod.default, {
      global: {
        stubs: { 'router-link': { template: '<a><slot /></a>' } },
      },
    })
    await flushPromises()

    const buttons = wrapper.findAll('button')
    const submitBtn = buttons.find(b => b.text().includes('提交覆盖'))
    expect(submitBtn).toBeTruthy()
    if (submitBtn) {
      expect(submitBtn.attributes('disabled')).toBeDefined()
    }
  })
})
