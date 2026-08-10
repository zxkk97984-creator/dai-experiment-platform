import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const pushMock = vi.hoisted(() => vi.fn())
const getGradesMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '5' } }),
  useRouter: () => ({ push: pushMock }),
  createRouter: () => ({ beforeEach: vi.fn(), afterEach: vi.fn(), currentRoute: { value: {} }, push: vi.fn() }),
  createWebHistory: () => ({}),
}))
vi.mock('../../../api/exams.js', () => ({ examsAPI: { getGrades: getGradesMock } }))
vi.mock('../../../stores/app.js', () => ({ useAppStore: () => ({ showToast: vi.fn() }) }))

import GradesView from '../GradesView.vue'

describe('考试成绩总览', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getGradesMock.mockResolvedValue({ data: {
      exam: { title: 'Python期中测验', course_title: 'Python程序设计' },
      summary: { expected_count: 2, submitted_count: 1, graded_count: 1, average_score: 92, highest_score: 92, pass_rate: 100, excellent_rate: 100 },
      distribution: [{ label: '90–100', count: 1 }, { label: '80–89', count: 0 }],
      items: [
        { id: 1, submission_id: 7, student_name: '爱丽丝', student_number: '2023001', status: 'graded', score: 92, submitted_at: '2026-08-09T10:00:00Z' },
        { id: 'absent-2', submission_id: null, student_name: '鲍勃', student_number: '2023002', status: 'absent', score: null },
      ],
    } })
  })

  it('展示统计、分布、缺考状态并进入成绩详情', async () => {
    const wrapper = mount(GradesView, { global: { stubs: { AppLayout: { template: '<div><slot /></div>' } } } })
    await flushPromises()
    expect(wrapper.text()).toContain('Python期中测验 · 成绩总览')
    expect(wrapper.text()).toContain('应考人数')
    expect(wrapper.text()).toContain('缺考')
    expect(wrapper.text()).toContain('分数分布')
    const detailButton = wrapper.findAll('button').find((button) => button.text() === '查看详情' && !button.attributes('disabled'))
    await detailButton.trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/teacher/exams/5/grades/7')
  })
})
