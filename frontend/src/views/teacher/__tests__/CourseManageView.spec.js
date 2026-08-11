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

vi.mock('../../../api/academics', () => ({
  academicsAPI: { listTerms: vi.fn() },
}))

vi.mock('../../../stores/app', () => ({
  useAppStore: () => ({ showToast: showToastMock }),
}))

import { coursesAPI } from '../../../api/courses.js'
import { academicsAPI } from '../../../api/academics.js'

function makeCourses(count) {
  return Array.from({ length: count }, (_, index) => ({
    id: index + 1,
    title: `课程 ${index + 1}`,
    description: `简介 ${index + 1}`,
    status: 'published',
    academic_term: { id: 1, name: '2026 秋' },
    teaching_classes: [{ id: 1, name: '软件 2601 班' }],
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
      stubs: {
        AppLayout: { template: '<div><slot /></div>' },
        CourseCreateModal: {
          emits: ['created'],
          template: '<div data-testid="course-create-modal"><button type="button" @click="$emit(\'created\', { id: 13 })">创建完成</button></div>',
        },
      },
    },
  })
}

describe('课程管理页 CourseManageView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    academicsAPI.listTerms.mockResolvedValue({ data: { items: [] } })
    coursesAPI.list.mockResolvedValue({ data: { items: [], total: 0, summary: {} } })
  })

  it('12 门课程分两页展示：第 1 页 10 行，点「第 2 页」后 2 行', async () => {
    coursesAPI.list.mockImplementation(({ page }) => Promise.resolve({
      data: {
        items: page === 2 ? makeCourses(2).map((course, index) => ({ ...course, id: index + 11 })) : makeCourses(10),
        total: 12,
        summary: { total: 12, published: 12, draft: 0, archived: 0 },
      },
    }))
    const wrapper = await mountPage()
    await flushPromises()

    expect(wrapper.findAll('tbody tr')).toHaveLength(10)
    expect(wrapper.find('footer.pagination-bar').text()).toContain('共 12 条')

    await wrapper.get('[aria-label="第 2 页"]').trigger('click')
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
  })

  it('切换筛选条件后回到第 1 页', async () => {
    coursesAPI.list.mockImplementation(({ page }) => Promise.resolve({
      data: { items: page === 2 ? makeCourses(2) : makeCourses(10), total: 12, summary: { total: 12, published: 12 } },
    }))
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
    coursesAPI.list.mockImplementation(({ status_filter: status }) => Promise.resolve({
      data: { items: status === 'archived' ? [] : makeCourses(2), total: status === 'archived' ? 0 : 2, summary: {} },
    }))
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.get('[aria-label="状态筛选"]').setValue('archived')
    await flushPromises()
    expect(wrapper.text()).toContain('暂无符合条件的课程')
  })

  it('点击创建课程后打开创建弹窗', async () => {
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.get('button.btn-primary').trigger('click')
    expect(wrapper.find('[data-testid="course-create-modal"]').exists()).toBe(true)
  })

  it('课程创建成功后进入课程设置页', async () => {
    const wrapper = await mountPage()
    await flushPromises()

    await wrapper.get('button.btn-primary').trigger('click')
    await wrapper.get('[data-testid="course-create-modal"] button').trigger('click')

    expect(pushMock).toHaveBeenCalledWith('/teacher/courses/13/manage')
  })
})
