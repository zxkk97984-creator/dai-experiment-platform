import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const push = vi.fn()
const showToast = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '4' } }),
  useRouter: () => ({ push }),
  createRouter: vi.fn(() => ({
    beforeEach: vi.fn(),
    afterEach: vi.fn(),
    beforeResolve: vi.fn(),
    push: vi.fn(),
    replace: vi.fn(),
    currentRoute: { value: { path: '/student/assignments/4' } },
  })),
  createWebHistory: vi.fn(() => ({})),
}))

vi.mock('../../../api/assignments.js', () => ({
  assignmentsAPI: {
    get: vi.fn(),
    getQuestions: vi.fn(),
  },
}))

vi.mock('../../../api/judge.js', () => ({
  judgeAPI: {
    list: vi.fn(),
    submit: vi.fn(),
    getResult: vi.fn(),
    sampleRun: vi.fn(),
  },
}))

vi.mock('../../../stores/app.js', () => ({
  useAppStore: () => ({ showToast }),
}))

import { assignmentsAPI } from '../../../api/assignments.js'
import { judgeAPI } from '../../../api/judge.js'

const activeBreakdown = {
  functional_score: 54,
  algorithm_score: 13,
  robustness_score: 7,
  quality_score: 5,
  raw_total: 79,
  score_cap: null,
  final_score_100: 79,
  strengths: ['核心功能已实现'],
  issues: ['边界处理不完整'],
  suggestions: ['考虑添加输入校验'],
}

let wrapper

function question(gradingMode) {
  return {
    id: 10,
    title: '混淆矩阵指标',
    description: '计算分类指标',
    function_name: 'confusion_metrics',
    starter_code: 'def confusion_metrics():\n    pass',
    public_cases: [],
    grading_mode: gradingMode,
  }
}

async function mountPage(gradingMode) {
  assignmentsAPI.get.mockResolvedValue({
    data: { id: 4, course_id: 1, title: '数据处理综合练习' },
  })
  assignmentsAPI.getQuestions.mockResolvedValue({
    data: { items: [question(gradingMode)] },
  })
  judgeAPI.list.mockResolvedValue({ data: { items: [] } })
  judgeAPI.submit.mockResolvedValue({ data: { id: 101 } })

  const mod = await import('../AssignmentDetailView.vue')
  wrapper = mount(mod.default, {
    global: {
      stubs: {
        AppLayout: { template: '<main><slot /></main>' },
      },
    },
  })
  await flushPromises()
}

async function submitCode() {
  const button = wrapper.findAll('button').find((item) => item.text().includes('提交代码'))
  expect(button).toBeTruthy()
  await button.trigger('click')
  await flushPromises()
}

describe('作业页 AI 判题结果', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
    vi.useRealTimers()
  })

  it('active 题持续轮询到 graded 明细并在当前页完整展示', async () => {
    judgeAPI.getResult
      .mockResolvedValueOnce({ data: { id: 101, status: 'running' } })
      .mockResolvedValueOnce({
        data: {
          id: 101,
          status: 'graded',
          score: 79,
          execution_time_ms: 512,
          grading_breakdown: activeBreakdown,
        },
      })

    await mountPage('active')
    await submitCode()

    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()
    expect(wrapper.text()).toContain('AI 评分中')

    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()

    const text = wrapper.text()
    expect(judgeAPI.getResult).toHaveBeenCalledTimes(2)
    expect(text).toContain('AI 评分详情')
    expect(text).toContain('功能正确性 F')
    expect(text).toContain('54 / 60')
    expect(text).toContain('算法关键步骤 A')
    expect(text).toContain('13 / 20')
    expect(text).toContain('最终得分 79')
    expect(text).toContain('核心功能已实现')
    expect(text).toContain('边界处理不完整')
    expect(text).toContain('考虑添加输入校验')
    expect(showToast).not.toHaveBeenCalledWith('判题超时，请重试', 'error')
  })

  it('shadow 题明确说明 AI 结果仅供教师复核且不泄露分项', async () => {
    judgeAPI.getResult.mockResolvedValue({
      data: { id: 101, status: 'accepted', score: 100, execution_time_ms: 707 },
    })

    await mountPage('shadow')
    await submitCode()
    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('影子评分')
    expect(text).toContain('AI 评分结果仅供教师复核')
    expect(text).not.toContain('AI 评分详情')
  })
})
