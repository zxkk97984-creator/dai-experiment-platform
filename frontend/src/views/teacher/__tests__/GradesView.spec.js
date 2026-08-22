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

  it('使用服务端分页和成绩筛选，不在当前页数组上伪造总数', async () => {
    getGradesMock.mockResolvedValue({ data: {
      exam: { title: '大班考试', course_title: '课程' },
      summary: { expected_count: 25, submitted_count: 25, graded_count: 25, average_score: 80, pass_rate: 80 },
      distribution: [],
      page: 1,
      page_size: 10,
      total: 25,
      items: [{ id: 1, submission_id: 1, student_name: '目标学生', student_number: '20260001', status: 'graded', score: 80 }],
    } })
    const wrapper = mount(GradesView, { global: { stubs: { AppLayout: { template: '<div><slot /></div>' } } } })
    await flushPromises()

    expect(getGradesMock).toHaveBeenCalledWith('5', { page: 1, page_size: 10, sort: 'score_desc' })
    const next = wrapper.find('button[aria-label="下一页"]')
    expect(next.exists()).toBe(true)
    await next.trigger('click')
    await flushPromises()
    expect(getGradesMock).toHaveBeenLastCalledWith('5', { page: 2, page_size: 10, sort: 'score_desc' })

    const search = wrapper.find('input[placeholder="搜索学生姓名或学号"]')
    await search.setValue('目标')
    await search.trigger('input')
    await wrapper.findAll('select')[0].setValue('graded')
    await wrapper.findAll('select')[1].setValue('excellent')
    await wrapper.findAll('select')[2].setValue('name')
    await flushPromises()
    expect(getGradesMock).toHaveBeenLastCalledWith('5', {
      page: 1,
      page_size: 10,
      q: '目标',
      status: 'graded',
      score: 'excellent',
      sort: 'name',
    })
    expect(wrapper.text()).toContain('共 25 条')
  })

  it('导出当前筛选条件下的全部服务端分页结果', async () => {
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:test')
    globalThis.URL.revokeObjectURL = vi.fn()
    getGradesMock.mockImplementation((_examId, params) => Promise.resolve({ data: {
      exam: { title: '大班考试' },
      total: 201,
      items: [{ id: params.page, student_name: `学生${params.page}`, student_number: `${params.page}`, status: 'graded', score: 80 }],
    } }))
    const wrapper = mount(GradesView, { global: { stubs: { AppLayout: { template: '<div><slot /></div>' } } } })
    await flushPromises()
    await wrapper.findAll('select')[0].setValue('graded')
    await wrapper.findAll('select')[1].setValue('good')
    await wrapper.findAll('select')[2].setValue('name')
    await wrapper.find('input[placeholder="搜索学生姓名或学号"]').setValue('目标')
    await wrapper.find('input[placeholder="搜索学生姓名或学号"]').trigger('input')
    await flushPromises()

    getGradesMock.mockClear()
    await wrapper.find('button.export-button').trigger('click')
    await flushPromises()

    expect(getGradesMock).toHaveBeenNthCalledWith(1, '5', {
      page: 1, page_size: 100, q: '目标', status: 'graded', score: 'good', sort: 'name',
    })
    expect(getGradesMock).toHaveBeenNthCalledWith(2, '5', {
      page: 2, page_size: 100, q: '目标', status: 'graded', score: 'good', sort: 'name',
    })
    expect(getGradesMock).toHaveBeenNthCalledWith(3, '5', {
      page: 3, page_size: 100, q: '目标', status: 'graded', score: 'good', sort: 'name',
    })
  })
})
