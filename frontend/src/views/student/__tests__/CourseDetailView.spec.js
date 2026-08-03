// 课程概览（参考图 03）：hero + 七个标签页；概览双栏（章节路径 | 任务/反馈/考试/公告）
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
    useRoute: () => ({ params: { id: '7' }, path: '/student/courses/7' }),
  }
})

const coursesMock = vi.hoisted(() => ({ get: vi.fn(), getChapters: vi.fn(), enroll: vi.fn() }))
const assignmentsMock = vi.hoisted(() => ({ list: vi.fn() }))
const examsMock = vi.hoisted(() => ({ list: vi.fn() }))
const dashboardMock = vi.hoisted(() => ({ student: vi.fn() }))
const toastMock = vi.hoisted(() => ({ showToast: vi.fn() }))

vi.mock('../../../api/courses.js', () => ({ coursesAPI: coursesMock }))
vi.mock('../../../api/assignments.js', () => ({ assignmentsAPI: assignmentsMock }))
vi.mock('../../../api/exams.js', () => ({ examsAPI: examsMock }))
vi.mock('../../../api/dashboard.js', () => ({ dashboardAPI: dashboardMock }))
vi.mock('../../../stores/app.js', () => ({ useAppStore: () => toastMock }))

import CourseDetailView from '../CourseDetailView.vue'

const course = {
  id: 7,
  title: '机器学习导论',
  description: '监督学习与模型评估',
  status: 'published',
  teacher_id: 5,
}

const chapters = [
  { id: 70, course_id: 7, title: '第一章 线性回归', order_index: 0, lessons: [{ id: 701, title: '回归基础', content_type: 'markdown' }] },
  { id: 71, course_id: 7, title: '第二章 决策树', order_index: 1, lessons: [{ id: 711, title: '树模型', content_type: 'markdown' }, { id: 712, title: '决策树实验', content_type: 'notebook' }] },
]

const assignments = [
  { id: 91, course_id: 7, title: '线性回归作业', description: '', status: 'published', due_at: '2026-08-10T15:00:00Z' },
]

const exams = [
  { id: 81, course_id: 7, title: '期中考试', status: 'published', starts_at: '2026-08-15T02:00:00Z', ends_at: '2026-08-15T04:00:00Z', duration_minutes: 120 },
]

const dashboardData = () => ({
  summary: { course_count: 1, pending_assignment_count: 1, upcoming_exam_count: 1, unread_announcement_count: 1 },
  priority_items: [
    { kind: 'assignment', id: 91, title: '线性回归作业', course_title: '机器学习导论', urgency: 'normal', route: '/student/assignments/91' },
  ],
  continue_learning: null,
  courses: [],
  recent_feedback: [
    { kind: 'experiment', id: 21, title: '实验反馈', course_title: '机器学习导论', score: 88, feedback: '思路清晰', graded_at: '2026-07-30T06:00:00Z', route: '/student/experiments/712' },
  ],
  announcements: [
    { id: 9, title: '机房调整', content: 'A302', priority: 'important', scope: 'course', course_id: 7, course_title: '机器学习导论', author_name: '王老师', published_at: '2026-08-01T04:00:00Z', expires_at: null, is_read: false },
  ],
})

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().setUser({ id: 1, username: 'stu', real_name: '测试生', role: 'student' })
  return mount(CourseDetailView, {
    global: {
      plugins: [pinia],
      stubs: { AppLayout: { template: '<main><slot /></main>' } },
    },
  })
}

function mockOk({ withDashboard = true } = {}) {
  coursesMock.get.mockResolvedValue({ data: course })
  coursesMock.getChapters.mockResolvedValue({ data: { items: chapters } })
  assignmentsMock.list.mockResolvedValue({ data: { items: assignments } })
  examsMock.list.mockResolvedValue({ data: { items: exams } })
  if (withDashboard) dashboardMock.student.mockResolvedValue({ data: dashboardData() })
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  coursesMock.get.mockReset()
  coursesMock.getChapters.mockReset()
  coursesMock.enroll.mockReset()
  assignmentsMock.list.mockReset()
  examsMock.list.mockReset()
  dashboardMock.student.mockReset()
})

describe('课程概览 CourseDetailView（参考图 03）', () => {
  it('面包屑、英雄元数据、进度与 CTA 渲染真实值', async () => {
    mockOk()
    // 课程共 3 课时，本地完成 1 个 → 33%
    localStorage.setItem('course_7_completed', JSON.stringify([701]))
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('机器学习导论')
    expect(wrapper.text()).toContain('监督学习与模型评估')
    expect(wrapper.text()).toContain('33%')
    expect(wrapper.get('.hero-continue-btn').text()).toContain('继续学习')
  })

  it('提供全部七个标签且可切换内容', async () => {
    mockOk()
    const wrapper = mountView()
    await flushPromises()
    const labels = wrapper.findAll('.course-tab').map((t) => t.text())
    expect(labels).toEqual(['概览', '章节内容', '作业', '实验', '考试', '公告', '成绩'])
    // 切到作业标签：渲染作业列表，英雄身份不变
    await wrapper.findAll('.course-tab').find((t) => t.text() === '作业').trigger('click')
    expect(wrapper.text()).toContain('线性回归作业')
    expect(wrapper.text()).toContain('机器学习导论')
  })

  it('概览左侧展示章节路径', async () => {
    mockOk()
    localStorage.setItem('course_7_completed', JSON.stringify([701]))
    const wrapper = mountView()
    await flushPromises()
    const rows = wrapper.findAll('.chapter-row')
    expect(rows.length).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('第一章 线性回归')
  })

  it('章节状态区分已完成/当前/锁定且可访问', async () => {
    mockOk()
    localStorage.setItem('course_7_completed', JSON.stringify([701]))
    const wrapper = mountView()
    await flushPromises()
    const rows = wrapper.findAll('.chapter-row')
    // 701 已完成；712（第一个未完成）为当前；其后为锁定
    expect(rows[0].classes()).toContain('is-completed')
    expect(rows[1].classes()).toContain('is-current')
    expect(rows[2].classes()).toContain('is-locked')
  })

  it('点击章节行进入既有课时路由', async () => {
    mockOk()
    localStorage.setItem('course_7_completed', JSON.stringify([701]))
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('.chapter-row')[0].trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/courses/7/lessons/701')
  })

  it('概览右侧展示待办、反馈、考试与公告摘要', async () => {
    mockOk()
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('线性回归作业')
    expect(wrapper.text()).toContain('88')
    expect(wrapper.text()).toContain('思路清晰')
    expect(wrapper.text()).toContain('期中考试')
    expect(wrapper.text()).toContain('机房调整')
  })

  it('作业与考试入口路由保持可用', async () => {
    mockOk()
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('.course-tab').find((t) => t.text() === '考试').trigger('click')
    await wrapper.get('.exam-row-link').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/exams/81')
  })

  it('课程反馈为空时显示明确空态', async () => {
    mockOk()
    dashboardMock.student.mockResolvedValue({
      data: { ...dashboardData(), recent_feedback: [], priority_items: [], announcements: [] },
    })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('暂无反馈')
  })

  it('403 未选课展示选课动作并触发选课', async () => {
    coursesMock.get.mockRejectedValueOnce(Object.assign(new Error('forbidden'), { response: { status: 403 } }))
    coursesMock.getChapters.mockResolvedValue({ data: { items: chapters } })
    assignmentsMock.list.mockResolvedValue({ data: { items: [] } })
    examsMock.list.mockResolvedValue({ data: { items: [] } })
    dashboardMock.student.mockResolvedValue({ data: dashboardData() })
    coursesMock.enroll.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('还未选这门课')
    await wrapper.get('.hero-enroll-btn').trigger('click')
    await flushPromises()
    expect(coursesMock.enroll).toHaveBeenCalledWith('7')
  })

  it('404 展示课程不存在并保留返回动作', async () => {
    coursesMock.get.mockRejectedValueOnce(Object.assign(new Error('not found'), { response: { status: 404 } }))
    coursesMock.getChapters.mockResolvedValue({ data: { items: [] } })
    assignmentsMock.list.mockResolvedValue({ data: { items: [] } })
    examsMock.list.mockResolvedValue({ data: { items: [] } })
    dashboardMock.student.mockResolvedValue({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('课程不存在')
    await wrapper.get('.back-list-btn').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/courses')
  })

  it('通用失败展示重试并保留恢复动作', async () => {
    coursesMock.get
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ data: course })
    coursesMock.getChapters.mockResolvedValue({ data: { items: chapters } })
    assignmentsMock.list.mockResolvedValue({ data: { items: assignments } })
    examsMock.list.mockResolvedValue({ data: { items: exams } })
    dashboardMock.student.mockResolvedValue({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('加载课程失败')
    await wrapper.get('.retry-btn').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('机器学习导论')
  })
})
