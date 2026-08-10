/** 课程管理页 CourseManageView 组件测试：列表加载、真实分页控件、筛选复位、创建课程 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const showToastMock = vi.hoisted(() => vi.fn())
const pushMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  createRouter: vi.fn(() => ({
    beforeEach: vi.fn(),
    afterEach: vi.fn(),
    beforeResolve: vi.fn(),
    push: pushMock,
    replace: vi.fn(),
    currentRoute: { value: { path: '/teacher/courses' } },
  })),
  createWebHistory: vi.fn(() => ({})),
}))

vi.mock('../../../api/courses', () => ({
  coursesAPI: { list: vi.fn(), create: vi.fn(), update: vi.fn() },
}))

vi.mock('../../../stores/app', () => ({
  useAppStore: () => ({ showToast: showToastMock }),
}))

import { coursesAPI } from '../../../api/courses.js'

function makeCourses(count) {
  return Array.from({ length: count }, (_, index) => ({
    id: index + 1,
    title: `课程 ${index + 1}`,
    description: `简介 ${index + 1}`,
    status: 'published',
    term: '2026 秋',
    chapter_count: 3,
    lesson_count: 8,
    student_count: 30,
    updated_at: `2026-08-0${(index % 9) + 1}T08:00:00Z`,
  }))
}

async function mountPage() {
  const mod = await import('../CourseManageView.vue')
  return mount(mod.default, {
    global: {
      stubs: { AppLayout: { template: '<div><slot /></div>' } },
    },
  })
}

describe('课程管理页 CourseManageView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    coursesAPI.list.mockResolvedValue({ data: { items: [] } })
  })

  it('12 门课程分两页展示：第 1 页 10 行，点「第 2 页」后 2 行', async () => {
    coursesAPI.list.mockResolvedValue({ data: { items: makeCourses(12) } })
    const wrapper = await mountPage()
    await flushPromises()

    expect(wrapper.findAll('tbody tr')).toHaveLength(10)
    expect(wrapper.find('footer.pagination-bar').text()).toContain('共 12 条')

    await wrapper.get('[aria-label="第 2 页"]').trigger('click')
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
  })

  it('切换筛选条件后回到第 1 页', async () => {
    coursesAPI.list.mockResolvedValue({ data: { items: makeCourses(12) } })
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.get('[aria-label="第 2 页"]').trigger('click')
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)

    await wrapper.get('[aria-label="排序"]').setValue('title')
    expect(wrapper.findAll('tbody tr')).toHaveLength(10)
    const pageOne = wrapper.find('[aria-label="第 1 页"]')
    expect(pageOne.exists()).toBe(true)
    expect(pageOne.attributes('aria-current')).toBe('page')
  })

  it('筛选后无结果时展示空态', async () => {
    coursesAPI.list.mockResolvedValue({ data: { items: makeCourses(2) } })
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.get('[aria-label="状态筛选"]').setValue('archived')
    expect(wrapper.text()).toContain('暂无符合条件的课程')
  })

  it('创建课程成功后刷新列表', async () => {
    coursesAPI.create.mockResolvedValue({ data: { id: 99 } })
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.get('button.btn-primary').trigger('click')
    await wrapper.get('input[placeholder="输入课程名称"]').setValue('数据结构')
    await wrapper.get('textarea[placeholder="输入课程简介"]').setValue('数据结构与算法')
    await wrapper.findAll('button.btn-primary').find((b) => b.text().includes('确认创建')).trigger('click')
    await flushPromises()

    expect(coursesAPI.create).toHaveBeenCalledWith({ title: '数据结构', description: '数据结构与算法' })
    expect(coursesAPI.list).toHaveBeenCalledTimes(2)
  })
})
