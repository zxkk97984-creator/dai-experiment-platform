// 任务中心：作业+考试+实验聚合；状态标签页、筛选、排序、表格与分页
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '../../../stores/auth.js'

const routerState = vi.hoisted(() => ({ push: vi.fn() }))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useRouter: () => ({ push: routerState.push }),
    useRoute: () => ({ path: '/student/assignments' }),
  }
})

const assignmentsMock = vi.hoisted(() => ({ list: vi.fn() }))
const examsMock = vi.hoisted(() => ({ list: vi.fn() }))
const experimentsMock = vi.hoisted(() => ({ listRecords: vi.fn() }))
const coursesMock = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock('../../../api/assignments.js', () => ({ assignmentsAPI: assignmentsMock }))
vi.mock('../../../api/exams.js', () => ({ examsAPI: examsMock }))
vi.mock('../../../api/experiments.js', () => ({ experimentsAPI: experimentsMock }))
vi.mock('../../../api/courses.js', () => ({ coursesAPI: coursesMock }))

import AssignmentListView from '../AssignmentListView.vue'

const DAY = 86400000
const future = (offsetDays) => new Date(Date.now() + offsetDays * DAY).toISOString()
const past = (offsetDays) => new Date(Date.now() - offsetDays * DAY).toISOString()

function mockSources({ failAssignment = false, failExam = false, failExperiment = false } = {}) {
  assignmentsMock.list.mockImplementation(() =>
    failAssignment
      ? Promise.reject(new Error('boom'))
      : Promise.resolve({
          data: {
            items: [
              // 作业1 已全部提交（后端 list_assignments 返回 is_submitted），任务中心应显示「已提交」
              { id: 1, title: '线性回归作业', course_id: 5, status: 'published', due_at: future(3), is_submitted: true },
              { id: 2, title: '决策树作业', course_id: 6, status: 'published', due_at: past(1) },
            ],
          },
        }),
  )
  examsMock.list.mockImplementation(() =>
    failExam
      ? Promise.reject(new Error('boom'))
      : Promise.resolve({
          data: {
            items: [
              { id: 3, title: '期中考试', course_id: 5, status: 'published', starts_at: future(2), ends_at: future(2) },
            ],
          },
        }),
  )
  experimentsMock.listRecords.mockImplementation(() =>
    failExperiment
      ? Promise.reject(new Error('boom'))
      : Promise.resolve({
          data: {
            items: [
              { id: 9, lesson_id: 712, title: '决策树实验', status: 'started', updated_at: future(0) },
            ],
          },
        }),
  )
  coursesMock.list.mockResolvedValue({
    data: {
      items: [
        { id: 5, title: '机器学习导论', status: 'published' },
        { id: 6, title: '数据结构', status: 'published' },
      ],
    },
  })
}

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().setUser({ id: 1, username: 'stu', real_name: '测试生', role: 'student' })
  return mount(AssignmentListView, {
    global: {
      plugins: [pinia],
      stubs: { AppLayout: { template: '<main><slot /></main>' } },
    },
  })
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
})

describe('任务中心 AssignmentListView（参考图 05）', () => {
  it('页头展示真实开放任务数与最近截止', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    // 全部任务 = 作业1（已提交）+ 作业2（逾期）+ 考试 + 实验 = 4
    expect(wrapper.get('.task-count').text()).toContain('4')
    expect(wrapper.get('.nearest-deadline').text()).toBeTruthy()
  })

  it('已全部提交的作业显示「已提交」而非「待办」', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    const row = wrapper.findAll('.task-table tbody tr').find((r) => r.text().includes('线性回归作业'))
    expect(row.text()).toContain('已提交')
    const tabs = wrapper.findAll('.status-tab')
    // 「已完成」标签计数为 1（仅作业1）
    expect(tabs[3].text()).toContain('1')
  })

  it('状态标签页显示计数且可切换', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    const tabs = wrapper.findAll('.status-tab')
    expect(tabs.length).toBe(4)
    expect(tabs[0].text()).toContain('全部')
    expect(tabs[1].text()).toContain('待办')
    expect(tabs[2].text()).toContain('逾期')
    expect(tabs[3].text()).toContain('已完成')
    // 切到逾期：只有决策树作业（past）
    await tabs[2].trigger('click')
    expect(wrapper.findAll('.task-table tbody tr').length).toBe(1)
    expect(wrapper.text()).toContain('决策树作业')
  })

  it('课程筛选仅显示所选课程任务', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.filter-course').setValue('5')
    const rows = wrapper.findAll('.task-table tbody tr')
    expect(rows.length).toBe(2)
    expect(wrapper.text()).toContain('线性回归作业')
    expect(wrapper.text()).toContain('期中考试')
    expect(wrapper.text()).not.toContain('决策树作业')
  })

  it('类型筛选仅显示所选类型任务', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.filter-kind').setValue('exam')
    const rows = wrapper.findAll('.task-table tbody tr')
    expect(rows.length).toBe(1)
    expect(wrapper.text()).toContain('期中考试')
  })

  it('排序按截止时间升序', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.filter-sort').setValue('due')
    const titles = wrapper.findAll('.task-name').map((t) => t.text())
    // 决策树作业逾期最早，其次考试（+2天），线性回归作业（+3天），实验无截止
    expect(titles[0]).toContain('决策树作业')
  })

  it('重置恢复默认筛选', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.filter-course').setValue('5')
    await wrapper.get('.filter-kind').setValue('exam')
    expect(wrapper.findAll('.task-table tbody tr').length).toBe(1)
    await wrapper.get('.reset-btn').trigger('click')
    expect(wrapper.findAll('.task-table tbody tr').length).toBe(4)
  })

  it('使用六列表格展示任务且不再按截止时间分组', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.findAll('thead th').map((node) => node.text())).toEqual([
      '任务名称', '所属课程', '类型', '状态', '截止时间', '操作',
    ])
    expect(wrapper.findAll('.task-table tbody tr')).toHaveLength(4)
    expect(wrapper.find('.task-group').exists()).toBe(false)
    expect(wrapper.get('.task-catalog-heading').text()).toContain('全部任务')
    expect(wrapper.get('.task-catalog-heading').text()).toContain('共 4 个')
  })

  it('每个任务 CTA 路由到既有学生路由', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('.task-action')[0].trigger('click')
    // 第一个任务是逾期最早的决策树作业
    expect(routerState.push).toHaveBeenCalledWith('/student/assignments/2')
    const examCta = wrapper.findAll('.task-table tbody tr').find((r) => r.text().includes('期中考试')).find('.task-action')
    await examCta.trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/exams/3')
    const expCta = wrapper.findAll('.task-table tbody tr').find((r) => r.text().includes('决策树实验')).find('.task-action')
    await expCta.trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/experiments/712')
  })

  it('单个来源失败不隐藏成功来源', async () => {
    mockSources({ failExam: true })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('线性回归作业')
    expect(wrapper.text()).toContain('决策树实验')
    expect(wrapper.text()).not.toContain('加载失败')
  })

  it('全部来源失败时展示错误并可重试', async () => {
    mockSources({ failAssignment: true, failExam: true, failExperiment: true })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('加载失败')
    mockSources()
    await wrapper.get('.retry-btn').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.task-table tbody tr').length).toBe(4)
  })

  it('所有任务操作使用与实验列表一致的轮廓按钮', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.findAll('.task-action')).toHaveLength(4)
    expect(wrapper.findAll('.task-action.btn-primary')).toHaveLength(0)
  })

  it('每页展示 10 条任务并可切换分页', async () => {
    mockSources()
    assignmentsMock.list.mockResolvedValue({
      data: {
        items: Array.from({ length: 12 }, (_, index) => ({
          id: index + 1,
          title: `分页作业${index + 1}`,
          course_id: 5,
          status: 'published',
          due_at: future(index + 1),
        })),
      },
    })
    examsMock.list.mockResolvedValue({ data: { items: [] } })
    experimentsMock.listRecords.mockResolvedValue({ data: { items: [] } })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.findAll('.task-table tbody tr')).toHaveLength(10)
    expect(wrapper.get('.pagination-total').text()).toContain('共 12 条')
    await wrapper.findAll('.page-number').find((node) => node.text() === '2').trigger('click')
    expect(wrapper.findAll('.task-table tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('分页作业11')
  })

  it('筛选变化后回到第一页', async () => {
    mockSources()
    assignmentsMock.list.mockResolvedValue({
      data: {
        items: Array.from({ length: 12 }, (_, index) => ({
          id: index + 1,
          title: `筛选作业${index + 1}`,
          course_id: index === 11 ? 6 : 5,
          status: 'published',
          due_at: future(index + 1),
        })),
      },
    })
    examsMock.list.mockResolvedValue({ data: { items: [] } })
    experimentsMock.listRecords.mockResolvedValue({ data: { items: [] } })

    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('.page-number').find((node) => node.text() === '2').trigger('click')
    await wrapper.get('.filter-course').setValue('6')

    expect(wrapper.find('.page-number.active').text()).toBe('1')
    expect(wrapper.findAll('.task-table tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('筛选作业12')
  })

  it('空结果显示空状态，缺失课程和截止时间使用占位符', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()

    const experimentRow = wrapper.findAll('.task-table tbody tr').find((row) => row.text().includes('决策树实验'))
    expect(experimentRow.find('[data-label="所属课程"]').text()).toBe('—')
    expect(experimentRow.find('[data-label="截止时间"]').text()).toBe('—')

    await wrapper.get('.filter-kind').setValue('experiment')
    await wrapper.get('.filter-course').setValue('5')
    expect(wrapper.text()).toContain('暂无任务')
    expect(wrapper.get('.task-catalog-heading').text()).toContain('共 0 个')
  })
})
