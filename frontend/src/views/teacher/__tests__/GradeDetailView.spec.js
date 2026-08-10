import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const detailMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '5', submissionId: '7' } }),
  useRouter: () => ({ push: vi.fn() }),
  createRouter: () => ({ beforeEach: vi.fn(), afterEach: vi.fn(), currentRoute: { value: {} }, push: vi.fn() }),
  createWebHistory: () => ({}),
}))
vi.mock('../../../api/exams.js', () => ({ examsAPI: { getGradeDetail: detailMock } }))
vi.mock('../../../stores/app.js', () => ({ useAppStore: () => ({ showToast: vi.fn() }) }))

import GradeDetailView from '../GradeDetailView.vue'

describe('学生成绩详情', () => {
  beforeEach(() => {
    detailMock.mockResolvedValue({ data: {
      exam: { title: 'Python期中测验', course_title: 'Python程序设计' },
      student: { name: '爱丽丝', number: '2023001' },
      submission: { score: 92, status: 'graded', submitted_at: '2026-08-09T10:00:00Z', elapsed_minutes: 45 },
      analysis: { objective_score: 32, objective_total: 40, code_score: 60, code_total: 60, question_count: 1, correct_count: 0 },
      answers: [{ id: 1, order_index: 0, question_type: 'single_choice', prompt: 'Python关键字是什么？', points: 10, score: 8, selected_options: ['A'] }],
    } })
  })

  it('展示学生信息、分项成绩并可展开作答', async () => {
    const wrapper = mount(GradeDetailView, { global: { stubs: { AppLayout: { template: '<div><slot /></div>' } } } })
    await flushPromises()
    expect(wrapper.text()).toContain('学生成绩详情')
    expect(wrapper.text()).toContain('爱丽丝')
    expect(wrapper.text()).toContain('客观题得分')
    const question = wrapper.findAll('button').find((button) => button.text().includes('Python关键字是什么'))
    await question.trigger('click')
    expect(wrapper.text()).toContain('学生答案')
    expect(wrapper.text()).toContain('A')
  })

  it('无失效的「导出报告」按钮，打印按钮调用 window.print', async () => {
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => {})
    const wrapper = mount(GradeDetailView, { global: { stubs: { AppLayout: { template: '<div><slot /></div>' } } } })
    await flushPromises()

    expect(wrapper.findAll('button').some((button) => button.text().includes('导出报告'))).toBe(false)

    const printButton = wrapper.findAll('button').find((button) => button.text().includes('打印 / 保存 PDF'))
    expect(printButton).toBeDefined()
    await printButton.trigger('click')
    expect(printSpy).toHaveBeenCalledTimes(1)
    printSpy.mockRestore()
  })
})
