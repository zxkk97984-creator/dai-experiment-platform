// 作业列表：仅展示作业；状态标签页、搜索、筛选、排序、表格与分页
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

function mockSources({ failAssignment = false, failCourses = false, assignmentItems } = {}) {
  assignmentsMock.list.mockImplementation(() =>
    failAssignment
      ? Promise.reject(new Error('boom'))
      : Promise.resolve({
          data: {
            items: assignmentItems || [
              // 作业1 已全部提交（后端 list_assignments 返回 is_submitted）
              { id: 1, title: '线性回归作业', course_id: 5, status: 'published', due_at: future(3), is_submitted: true },
              { id: 2, title: '决策树作业', course_id: 6, status: 'published', due_at: past(1) },
            ],
          },
        }),
  )
  examsMock.list.mockResolvedValue({
    data: {
      items: [
        { id: 3, title: '期中考试', course_id: 5, status: 'published', starts_at: future(2), ends_at: future(2) },
      ],
    },
  })
  experimentsMock.listRecords.mockResolvedValue({
    data: {
      items: [
        { id: 9, lesson_id: 712, title: '决策树实验', status: 'started', updated_at: future(0) },
      ],
    },
  })
  coursesMock.list.mockImplementation(() =>
    failCourses
      ? Promise.reject(new Error('boom'))
      : Promise.resolve({
          data: {
            items: [
              { id: 5, title: '机器学习导论', status: 'published' },
              { id: 6, title: '数据结构', status: 'published' },
            ],
          },
        }),
  )
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

describe('作业列表 AssignmentListView', () => {
  it('页头展示真实作业数与最近截止', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    // 全部作业 = 作业1（已提交）+ 作业2（逾期）= 2
    expect(wrapper.get('.assignment-count').text()).toContain('2')
    expect(wrapper.get('.nearest-deadline').text()).toBeTruthy()
  })

  it('只请求作业数据，不加载考试和实验，也不展示类型筛选', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()

    expect(assignmentsMock.list).toHaveBeenCalledTimes(1)
    expect(examsMock.list).not.toHaveBeenCalled()
    expect(experimentsMock.listRecords).not.toHaveBeenCalled()
    expect(wrapper.find('.filter-kind').exists()).toBe(false)
    expect(wrapper.findAll('thead th').map((node) => node.text())).not.toContain('类型')
    expect(wrapper.text()).not.toContain('期中考试')
    expect(wrapper.text()).not.toContain('决策树实验')
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

  it('课程筛选仅显示所选课程作业', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.filter-course').setValue('5')
    const rows = wrapper.findAll('.task-table tbody tr')
    expect(rows.length).toBe(1)
    expect(wrapper.text()).toContain('线性回归作业')
    expect(wrapper.text()).not.toContain('决策树作业')
  })

  it('按作业名称搜索仅显示匹配的作业', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.assignment-search-input').setValue('决策树')
    const rows = wrapper.findAll('.task-table tbody tr')
    expect(rows.length).toBe(1)
    expect(wrapper.text()).toContain('决策树作业')
    expect(wrapper.text()).not.toContain('线性回归作业')
  })

  it('排序按截止时间升序', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.filter-sort').setValue('due')
    const titles = wrapper.findAll('.task-name').map((t) => t.text())
    // 决策树作业逾期最早，其次线性回归作业（+3天）
    expect(titles[0]).toContain('决策树作业')
  })

  it('重置恢复默认筛选', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.filter-course').setValue('5')
    await wrapper.get('.assignment-search-input').setValue('线性')
    expect(wrapper.findAll('.task-table tbody tr').length).toBe(1)
    await wrapper.get('.reset-btn').trigger('click')
    expect(wrapper.findAll('.task-table tbody tr').length).toBe(2)
  })

  it('使用五列表格展示作业且不再按截止时间分组', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.findAll('thead th').map((node) => node.text())).toEqual([
      '作业名称', '所属课程', '状态', '截止时间', '操作',
    ])
    expect(wrapper.findAll('.task-table tbody tr')).toHaveLength(2)
    expect(wrapper.find('.task-group').exists()).toBe(false)
    expect(wrapper.get('.task-catalog-heading').text()).toContain('全部作业')
    expect(wrapper.get('.task-catalog-heading').text()).toContain('共 2 个')
  })

  it('每个作业 CTA 路由到既有学生路由', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('.task-action')[0].trigger('click')
    // 第一个作业是逾期最早的决策树作业
    expect(routerState.push).toHaveBeenCalledWith('/student/assignments/2')
    const assignmentCta = wrapper.findAll('.task-table tbody tr').find((r) => r.text().includes('线性回归作业')).find('.task-action')
    await assignmentCta.trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/assignments/1')
  })

  it('课程数据失败时仍展示作业', async () => {
    mockSources({ failCourses: true })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('线性回归作业')
    expect(wrapper.text()).toContain('决策树作业')
    expect(wrapper.text()).not.toContain('加载失败')
  })

  it('作业来源失败时展示错误并可重试', async () => {
    mockSources({ failAssignment: true })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('加载失败')
    mockSources()
    await wrapper.get('.retry-btn').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.task-table tbody tr').length).toBe(2)
  })

  it('所有作业操作使用轮廓按钮', async () => {
    mockSources()
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.findAll('.task-action')).toHaveLength(2)
    expect(wrapper.findAll('.task-action.btn-primary')).toHaveLength(0)
  })

  it('每页展示 10 条作业并可切换分页', async () => {
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
    mockSources({
      assignmentItems: [
        { id: 10, title: '无课程作业', status: 'published', is_submitted: false },
      ],
    })
    const wrapper = mountView()
    await flushPromises()

    const assignmentRow = wrapper.findAll('.task-table tbody tr').find((row) => row.text().includes('无课程作业'))
    expect(assignmentRow.find('[data-label="所属课程"]').text()).toBe('—')
    expect(assignmentRow.find('[data-label="截止时间"]').text()).toBe('—')

    await wrapper.get('.assignment-search-input').setValue('不存在')
    expect(wrapper.text()).toContain('暂无作业')
    expect(wrapper.get('.task-catalog-heading').text()).toContain('共 0 个')
  })
})
