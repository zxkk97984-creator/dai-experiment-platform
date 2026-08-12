import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const router = { push: vi.fn(), replace: vi.fn() }
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '3' } }),
  useRouter: () => router,
  onBeforeRouteLeave: vi.fn(),
  createRouter: vi.fn(() => ({ beforeEach: vi.fn(), afterEach: vi.fn(), beforeResolve: vi.fn(), push: vi.fn(), replace: vi.fn(), currentRoute: { value: { path: '/student/exams/3' } } })),
  createWebHistory: vi.fn(() => ({})),
}))

vi.mock('../../../api/exams.js', () => ({
  examsAPI: {
    getSession: vi.fn(), saveAnswers: vi.fn(), submit: vi.fn(), start: vi.fn(),
  },
}))

vi.mock('../../../stores/app.js', () => ({ useAppStore: () => ({ showToast: vi.fn() }) }))

import { examsAPI } from '../../../api/exams.js'
import ExamView from '../ExamView.vue'

const SERVER_NOW = '2026-08-12T04:00:00Z'
const QUESTIONS = [
  { id: 1, question_type: 'single_choice', prompt: '2 + 2 = ?', options: { A: '4', B: '5' }, points: 10 },
  { id: 2, question_type: 'fill_blank', prompt: '作者是 [[blank:blank1]]', points: 20 },
]

function sessionFor(status, extra = {}) {
  const active = status === 'started'
  return {
    server_now: SERVER_NOW,
    exam: { id: 3, title: '期中考试', duration_minutes: 60, max_score: 30, student_status: active ? 'in_progress' : 'graded', ...extra.exam },
    submission: {
      id: 7, status, score: null, score_visible: false,
      expires_at: active ? '2026-08-12T04:10:00Z' : '2026-08-12T04:00:00Z',
      submitted_at: active ? null : SERVER_NOW, submission_reason: 'manual', ...extra.submission,
    },
    questions: active || extra.visibility?.questions ? QUESTIONS : [],
    saved_answers: [],
    visibility: { score: false, questions: false, answers: false, review_released: false, ...extra.visibility },
  }
}

async function mountExam(status, extra = {}) {
  examsAPI.getSession.mockResolvedValue({ data: sessionFor(status, extra) })
  const wrapper = mount(ExamView, { global: { stubs: { AppLayout: { template: '<div><slot /></div>' }, ConfirmDialog: { template: '<div class="confirm-stub" />' } } } })
  await flushPromises()
  return wrapper
}

describe('ExamView 安全状态与结果展示', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    examsAPI.saveAnswers.mockResolvedValue({ data: { server_now: SERVER_NOW, results: [{ question_id: 1, ok: true, version: 1 }] } })
  })
  afterEach(() => vi.useRealTimers())

  it('待复核显示人工处理提示，不泄露系统细节', async () => {
    const wrapper = await mountExam('review_required')
    expect(wrapper.text()).toContain('已交卷，等待教师复核')
    expect(wrapper.text()).toContain('不会按 0 分计入')
    expect(wrapper.text()).not.toContain('system_error')
    wrapper.unmount()
  })

  it('成绩未公开时不把 null 渲染成 0 分', async () => {
    const wrapper = await mountExam('graded', { submission: { score: null, score_visible: false } })
    expect(wrapper.text()).toContain('成绩暂未开放')
    expect(wrapper.text()).not.toContain('0 / 30')
    wrapper.unmount()
  })

  it('成绩公开时使用服务端 max_score', async () => {
    const wrapper = await mountExam('graded', { submission: { score: 25, score_visible: true }, visibility: { score: true } })
    expect(wrapper.text()).toContain('25 / 30 分')
    wrapper.unmount()
  })

  it('进行中恢复题目并安全渲染填空输入框', async () => {
    const wrapper = await mountExam('started')
    expect(wrapper.find('.workspace').exists()).toBe(true)
    expect(wrapper.find('input[aria-label="填空 blank1"]').exists()).toBe(true)
    expect(wrapper.html()).not.toContain('v-html')
    wrapper.unmount()
  })

  it('答案变更在 800ms 防抖后走批量保存并携带版本', async () => {
    vi.useFakeTimers()
    const wrapper = await mountExam('started')
    await wrapper.get('input[type="radio"]').trigger('change')
    await vi.advanceTimersByTimeAsync(801)
    await flushPromises()
    expect(examsAPI.saveAnswers).toHaveBeenCalledWith(3, [expect.objectContaining({ question_id: 1, selected_options: ['A'], expected_version: 0 })])
    wrapper.unmount()
  })

  it('刷新后若剩余不足一分钟立即提醒，并在 3 秒后关闭', async () => {
    vi.useFakeTimers()
    const wrapper = await mountExam('started', { submission: { expires_at: '2026-08-12T04:00:50Z' } })
    expect(wrapper.find('.minute-warning').exists()).toBe(true)
    await vi.advanceTimersByTimeAsync(3001)
    expect(wrapper.find('.minute-warning').exists()).toBe(false)
    wrapper.unmount()
  })
})
