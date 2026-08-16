import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../../../api/experiments.js', () => ({
  experimentsAPI: { listSubmissions: vi.fn() },
}))

vi.mock('../../../stores/auth.js', () => ({
  useAuthStore: () => ({ isAdmin: false, isTeacher: true }),
}))

const { routerPush } = vi.hoisted(() => ({ routerPush: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, path: '/teacher/submissions' }),
  useRouter: () => ({ push: routerPush }),
}))

import { experimentsAPI } from '../../../api/experiments.js'
import ExperimentSubmissionsView from '../ExperimentSubmissionsView.vue'

const LIST_RESPONSE = {
  items: [
    {
      id: 11,
      student_name: '张三',
      student_username: '20260001',
      course_id: 3,
      course_name: '机器学习实践',
      entry_id: 8,
      entry_name: '数据分析入门',
      entry_type: 'lesson',
      attempt_number: 1,
      submitted_at: '2026-08-07T01:54:33Z',
      score: null,
    },
    {
      id: 12,
      student_name: '李四',
      student_username: '20260002',
      course_id: 3,
      course_name: '机器学习实践',
      entry_id: 9,
      entry_name: 'Notebook 实验',
      entry_type: 'lesson',
      attempt_number: 2,
      submitted_at: '2026-08-06T01:54:33Z',
      score: 96,
    },
  ],
  total: 2,
  page: 1,
  page_size: 10,
  summary: { total: 8, pending: 3, graded: 5 },
  filter_options: {
    courses: [{ id: 3, name: '机器学习实践' }],
    entries: [{ id: 8, name: '数据分析入门' }, { id: 9, name: 'Notebook 实验' }],
  },
}

function mountPage() {
  return mount(ExperimentSubmissionsView, {
    global: {
      stubs: {
        AppLayout: { template: '<main><slot /></main>' },
        AppIcon: { template: '<i class="icon-stub" />' },
      },
    },
  })
}

describe('实验提交与评分列表', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    experimentsAPI.listSubmissions.mockResolvedValue({ data: LIST_RESPONSE })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('展示三项统计、表格状态和对应操作', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('提交与评分')
    const metrics = wrapper.findAll('.submissions-strip .metric').map((m) => m.text())
    expect(metrics[0]).toContain('8')
    expect(metrics[0]).toContain('全部提交')
    expect(metrics[1]).toContain('3')
    expect(metrics[1]).toContain('待评分')
    expect(metrics[2]).toContain('5')
    expect(metrics[2]).toContain('已评分')
    expect(text).toContain('张三')
    expect(text).toContain('20260001')
    expect(text).toContain('机器学习实践')
    expect(text).toContain('去评分')
    expect(text).toContain('查看详情')
  })

  it('快速筛选时旧响应晚返回不会覆盖新结果', async () => {
    vi.useFakeTimers()
    let resolveFirst
    let resolveSecond
    experimentsAPI.listSubmissions
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve }))
    const wrapper = mountPage()
    await flushPromises()

    // 输入搜索词 → 防抖后发出第二个请求（新）
    await wrapper.find('input[type="search"]').setValue('张三')
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()
    expect(experimentsAPI.listSubmissions).toHaveBeenNthCalledWith(2, expect.objectContaining({ q: '张三' }))

    // 新请求先返回：搜索后无结果
    resolveSecond({ data: { ...LIST_RESPONSE, items: [], total: 0, summary: { total: 0, pending: 0, graded: 0 } } })
    await flushPromises()
    expect(wrapper.text()).not.toContain('李四')
    expect(wrapper.text()).toContain('没有符合条件的提交')

    // 旧请求后返回全量列表——不得覆盖新结果
    resolveFirst({ data: LIST_RESPONSE })
    await flushPromises()
    expect(wrapper.text()).not.toContain('李四')
    expect(wrapper.text()).toContain('没有符合条件的提交')
  })

  it('搜索防抖并传递课程、实验、状态与排序参数', async () => {
    vi.useFakeTimers()
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('input[type="search"]').setValue('张三')
    await wrapper.find('select[aria-label="按课程筛选"]').setValue('3')
    await wrapper.find('select[aria-label="按实验筛选"]').setValue('8')
    await wrapper.find('select[aria-label="按评分状态筛选"]').setValue('pending')
    await wrapper.find('select[aria-label="提交记录排序"]').setValue('submitted_asc')
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()

    expect(experimentsAPI.listSubmissions).toHaveBeenLastCalledWith(expect.objectContaining({
      q: '张三',
      course_id: 3,
      entry_id: 8,
      review_status: 'pending',
      sort: 'submitted_asc',
      page: 1,
      page_size: 10,
    }))
  })

  it('点击待评分操作进入教师详情页', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const action = wrapper.findAll('.row-action').find((button) => button.text() === '去评分')
    await action.trigger('click')
    expect(routerPush).toHaveBeenCalledWith('/teacher/submissions/11')
  })

  it('接口失败时显示重试状态', async () => {
    experimentsAPI.listSubmissions.mockRejectedValueOnce(new Error('network'))
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('提交记录暂时无法加载')
    expect(wrapper.text()).toContain('重新加载')
  })
})
