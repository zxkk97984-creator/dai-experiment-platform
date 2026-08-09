// 我的课程（参考图 02）：标题 + 状态标签页 + 搜索 + 横向课程行 + 真实进度
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
    useRoute: () => ({ path: '/student/courses' }),
  }
})

const coursesMock = vi.hoisted(() => ({ list: vi.fn(), getChapters: vi.fn(), enroll: vi.fn() }))
const toastMock = vi.hoisted(() => ({ showToast: vi.fn() }))

vi.mock('../../../api/courses.js', () => ({ coursesAPI: coursesMock }))
vi.mock('../../../stores/app.js', () => ({
  useAppStore: () => toastMock,
}))

import CourseListView from '../CourseListView.vue'

const coursesData = () => ({
  items: [
    { id: 1, title: 'Python 编程基础', description: '从零开始的 Python 入门课', status: 'published', teacher_id: 4, is_enrolled: true, can_enroll: false },
    { id: 2, title: '机器学习导论', description: '监督学习与模型评估', status: 'published', teacher_id: 5, is_enrolled: false, can_enroll: true },
  ],
  total: 2,
})

const chaptersFor = (id) => ({
  items: [{ id: id * 10, lessons: [{ id: id * 100 + 1, title: `课程${id}第一课` }, { id: id * 100 + 2, title: `课程${id}第二课` }] }],
})

// 默认按课程 id 返回各自的章节，避免不同课程共用同一份章节数据
function mockChaptersPerCourse() {
  coursesMock.getChapters.mockImplementation((courseId) =>
    Promise.resolve({ data: chaptersFor(courseId) }),
  )
}

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().setUser({ id: 1, username: 'stu', real_name: '测试生', role: 'student' })
  return mount(CourseListView, {
    global: {
      plugins: [pinia],
      stubs: { AppLayout: { template: '<main><slot /></main>' } },
    },
  })
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  coursesMock.list.mockReset()
  coursesMock.getChapters.mockReset()
  coursesMock.enroll.mockReset()
})

describe('我的课程 CourseListView（参考图 02）', () => {
  it('标题为“我的课程”并带副标题', async () => {
    coursesMock.list.mockResolvedValue({ data: coursesData() })
    mockChaptersPerCourse()
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.get('.page-title').text()).toBe('我的课程')
    expect(wrapper.get('.page-sub').exists()).toBe(true)
  })

  it('提供 进行中 / 已完成 / 全部课程 三个标签页', async () => {
    coursesMock.list.mockResolvedValue({ data: coursesData() })
    mockChaptersPerCourse()
    const wrapper = mountView()
    await flushPromises()
    const tabs = wrapper.findAll('.tab-btn').map((t) => t.text())
    expect(tabs).toContain('进行中')
    expect(tabs).toContain('已完成')
    expect(tabs).toContain('全部课程')
  })

  it('搜索按课程标题过滤', async () => {
    coursesMock.list.mockResolvedValue({ data: coursesData() })
    mockChaptersPerCourse()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.search-input').setValue('Python')
    expect(wrapper.findAll('.course-row').length).toBe(1)
    expect(wrapper.text()).toContain('Python 编程基础')
    expect(wrapper.text()).not.toContain('机器学习导论')
  })

  it('每个课程行包含 identity、进度与下一步动作', async () => {
    coursesMock.list.mockResolvedValue({ data: coursesData() })
    mockChaptersPerCourse()
    localStorage.setItem('course_1_completed', JSON.stringify([101]))
    const wrapper = mountView()
    await flushPromises()
    const row = wrapper.get('.course-row')
    expect(row.find('.course-identity').exists()).toBe(true)
    expect(row.find('.ui-progress').exists()).toBe(true)
    expect(row.text()).toContain('50%')
    expect(row.find('.course-row-action').exists()).toBe(true)
  })

  it('本地存储损坏时进度降级为 0 且课程仍然显示', async () => {
    coursesMock.list.mockResolvedValue({ data: coursesData() })
    mockChaptersPerCourse()
    localStorage.setItem('course_1_completed', '{broken')
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.findAll('.course-row').length).toBe(2)
    expect(wrapper.text()).toContain('Python 编程基础')
  })

  it('未选课程（is_enrolled=false）不发章节请求：显示选课按钮且进度为 0', async () => {
    coursesMock.list.mockResolvedValue({ data: coursesData() })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersFor(1) })
    coursesMock.enroll.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    // 只对已选课程（id=1）请求章节
    expect(coursesMock.getChapters).toHaveBeenCalledTimes(1)
    expect(coursesMock.getChapters).toHaveBeenCalledWith(1)
    const rows = wrapper.findAll('.course-row')
    expect(rows.length).toBe(2)
    const unenrolled = rows[1]
    expect(unenrolled.text()).toContain('选课')
    expect(unenrolled.text()).toContain('尚未加入')
  })

  it('选课成功后重新拉取课程列表（以服务端 is_enrolled 为准）', async () => {
    coursesMock.list
      .mockResolvedValueOnce({ data: coursesData() })
      .mockResolvedValueOnce({
        data: {
          items: [
            { id: 1, title: 'Python 编程基础', is_enrolled: true, can_enroll: false },
            { id: 2, title: '机器学习导论', is_enrolled: true, can_enroll: false },
          ],
          total: 2,
        },
      })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersFor(1) })
    coursesMock.enroll.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    const rows = wrapper.findAll('.course-row')
    expect(rows[1].text()).toContain('选课')
    await rows[1].get('.enroll-btn').trigger('click')
    await flushPromises()
    expect(coursesMock.enroll).toHaveBeenCalledWith(2)
    // 重新拉取列表后再抓取章节
    expect(coursesMock.list).toHaveBeenCalledTimes(2)
    expect(coursesMock.getChapters).toHaveBeenCalledWith(2)
    expect(wrapper.findAll('.course-row')[1].text()).not.toContain('选课')
  })

  it('选课被拒绝显示服务端错误且保留当前列表', async () => {
    coursesMock.list.mockResolvedValue({ data: coursesData() })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersFor(1) })
    coursesMock.enroll.mockRejectedValue(
      Object.assign(new Error('forbidden'), { response: { status: 403, data: { detail: { message: '你已被移出白名单' } } } }),
    )
    const wrapper = mountView()
    await flushPromises()
    const rows = wrapper.findAll('.course-row')
    await rows[1].get('.enroll-btn').trigger('click')
    await flushPromises()
    expect(toastMock.showToast).toHaveBeenCalledWith('你已被移出白名单', 'error')
    expect(wrapper.findAll('.course-row').length).toBe(2)
  })

  it('“进行中”标签页只显示有真实进度的课程', async () => {
    coursesMock.list.mockResolvedValue({ data: coursesData() })
    mockChaptersPerCourse()
    localStorage.setItem('course_1_completed', JSON.stringify([101]))
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('.tab-btn').find((t) => t.text() === '进行中').trigger('click')
    expect(wrapper.findAll('.course-row').length).toBe(1)
    expect(wrapper.text()).toContain('Python 编程基础')
  })

  it('“已完成”标签页显示 100% 进度课程', async () => {
    coursesMock.list.mockResolvedValue({ data: coursesData() })
    mockChaptersPerCourse()
    localStorage.setItem('course_1_completed', JSON.stringify([101, 102]))
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('.tab-btn').find((t) => t.text() === '已完成').trigger('click')
    expect(wrapper.findAll('.course-row').length).toBe(1)
    expect(wrapper.text()).toContain('Python 编程基础')
  })

  it('已选课课程行跳转课程详情', async () => {
    coursesMock.list.mockResolvedValue({ data: coursesData() })
    mockChaptersPerCourse()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('.course-row-link')[0].trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/courses/1')
  })

  it('请求失败展示错误并可重试', async () => {
    coursesMock.list
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ data: coursesData() })
    mockChaptersPerCourse()
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('加载失败')
    await wrapper.get('.retry-btn').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.course-row').length).toBe(2)
  })

  it('空课程列表展示如实空态', async () => {
    coursesMock.list.mockResolvedValue({ data: { items: [], total: 0 } })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('暂无课程')
  })

  it('单个课程章节失败不导致整页错误（其余行正常）', async () => {
    coursesMock.list.mockResolvedValue({ data: coursesData() })
    coursesMock.getChapters
      .mockResolvedValueOnce({ data: chaptersFor(1) })
      .mockRejectedValueOnce(new Error('boom'))
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.findAll('.course-row').length).toBe(2)
    expect(wrapper.text()).not.toContain('加载失败')
  })

  it('受管封面 key 渲染为公开媒体 URL，无封面课程保留图标占位', async () => {
    coursesMock.list.mockResolvedValue({
      data: {
        items: [
          { id: 1, title: 'Python 编程基础', description: 'x', status: 'published', teacher_id: 4, is_enrolled: true, can_enroll: false, cover: 'covers/1/abc.webp' },
          { id: 2, title: '机器学习导论', description: 'y', status: 'published', teacher_id: 5, is_enrolled: false, can_enroll: true },
        ],
        total: 2,
      },
    })
    mockChaptersPerCourse()
    const wrapper = mountView()
    await flushPromises()

    const imgs = wrapper.findAll('.course-identity__cover')
    expect(imgs.length).toBe(1)
    expect(imgs[0].attributes('src')).toBe('/api/v1/media/course-covers/1?v=covers%2F1%2Fabc.webp')
    expect(imgs[0].attributes('alt')).toBe('Python 编程基础课程封面')
    // 无封面课程保留语义图标占位
    expect(wrapper.findAll('.course-identity__icon').length).toBe(1)
  })

  it('未选课课程也能显示公开封面', async () => {
    coursesMock.list.mockResolvedValue({
      data: {
        items: [
          { id: 2, title: '机器学习导论', description: 'y', status: 'published', teacher_id: 5, is_enrolled: false, can_enroll: true, cover: 'covers/2/def.png' },
        ],
        total: 1,
      },
    })
    coursesMock.getChapters.mockResolvedValue({ data: { items: [] } })
    const wrapper = mountView()
    await flushPromises()

    const row = wrapper.get('.course-row')
    expect(row.text()).toContain('选课')
    const img = row.find('.course-identity__cover')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('/api/v1/media/course-covers/2?v=covers%2F2%2Fdef.png')
  })
})
