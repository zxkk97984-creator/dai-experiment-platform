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
    useRoute: () => ({ path: '/student' }),
  }
})

const studentMock = vi.hoisted(() => ({ student: vi.fn() }))
const markReadMock = vi.hoisted(() => ({ markRead: vi.fn() }))

vi.mock('../../../api/dashboard.js', () => ({ dashboardAPI: studentMock }))
vi.mock('../../../api/announcements.js', () => ({ announcementsAPI: markReadMock }))

import DashboardView from '../DashboardView.vue'

const dashboardData = () => ({
  summary: {
    course_count: 2,
    pending_assignment_count: 1,
    upcoming_exam_count: 1,
    unread_announcement_count: 2,
  },
  priority_items: [
    {
      kind: 'assignment',
      id: 4,
      title: '特征工程',
      course_title: '机器学习导论',
      time_at: '2026-08-02T15:59:00Z',
      urgency: 'urgent',
      route: '/student/assignments/4',
    },
  ],
  continue_learning: {
    kind: 'lesson_experiment',
    title: '决策树实验',
    subtitle: '机器学习导论',
    updated_at: '2026-08-01T05:10:00Z',
    route: '/student/courses/2/notebook/8',
  },
  courses: [
    {
      id: 2,
      title: '机器学习导论',
      pending_assignment_count: 1,
      upcoming_exam_count: 1,
      last_activity_at: '2026-08-01T05:10:00Z',
      route: '/student/courses/2',
    },
  ],
  recent_feedback: [
    {
      kind: 'experiment',
      id: 21,
      title: '决策树实验反馈',
      course_title: '机器学习导论',
      score: 92,
      feedback: '特征选择解释清晰。',
      graded_at: '2026-08-01T06:00:00Z',
      route: '/student/experiments/7',
    },
  ],
  announcements: [
    {
      id: 9,
      title: '实验课机房调整',
      content: '本周实验课调整到 A302。',
      priority: 'important',
      scope: 'course',
      course_id: 2,
      course_title: '机器学习导论',
      author_name: '王老师',
      published_at: '2026-08-01T04:00:00Z',
      expires_at: null,
      is_read: false,
    },
  ],
})

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().setUser({ id: 1, username: 'stu', real_name: '张同学', role: 'student' })
  return mount(DashboardView, {
    global: {
      plugins: [pinia],
      stubs: { AppLayout: { template: '<main><slot /></main>' } },
    },
  })
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  studentMock.student.mockReset()
  markReadMock.markRead.mockReset()
})

describe('学生首页 DashboardView', () => {
  it('挂载时请求一次聚合数据', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    mountView()
    await flushPromises()
    expect(studentMock.student).toHaveBeenCalledTimes(1)
  })

  it('展示真实摘要计数与旧 mock 数字', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('待交作业')
    expect(wrapper.text()).toContain('即将考试')
    expect(wrapper.text()).toContain('未读公告')
    expect(wrapper.text()).toContain('特征工程')
    expect(wrapper.text()).not.toContain('进行中课程')
    expect(wrapper.text()).not.toContain('今日学习目标')
    expect(wrapper.text()).not.toContain('快速入口')
  })

  it('优先项按服务端顺序展示', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    const items = wrapper.findAll('.priority-item')
    expect(items[0].text()).toContain('特征工程')
    expect(items[0].text()).toContain('紧急')
  })

  it('继续学习按钮跳转服务端续学路由', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.continue-btn').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/courses/2/notebook/8')
  })

  it('课程快照跳转课程路由', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.course-snap-link').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/courses/2')
  })

  it('最新反馈展示真实评分与评语', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('最新反馈')
    expect(wrapper.text()).toContain('特征选择解释清晰。')
    expect(wrapper.text()).toContain('92')
  })

  it('公告渲染且标记已读后本地更新', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    markReadMock.markRead.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('实验课机房调整')
    await wrapper.get('.mark-read-btn').trigger('click')
    expect(markReadMock.markRead).toHaveBeenCalledWith(9)
    await flushPromises()
    expect(wrapper.find('.mark-read-btn').exists()).toBe(false)
  })

  it('标记已读后未读公告计数安全减一', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    markReadMock.markRead.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    const summaryNums = () => wrapper.findAll('.summary-num').map((n) => n.text())
    expect(summaryNums()[3]).toBe('2')
    await wrapper.get('.mark-read-btn').trigger('click')
    await flushPromises()
    expect(summaryNums()[3]).toBe('1')
  })

  it('请求失败展示错误并可重试', async () => {
    studentMock.student
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('加载失败')
    await wrapper.get('.retry-btn').trigger('click')
    await flushPromises()
    expect(studentMock.student).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('特征工程')
  })

  it('空数据展示如实空态', async () => {
    studentMock.student.mockResolvedValue({
      data: {
        summary: {
          course_count: 0,
          pending_assignment_count: 0,
          upcoming_exam_count: 0,
          unread_announcement_count: 0,
        },
        priority_items: [],
        continue_learning: null,
        courses: [],
        recent_feedback: [],
        announcements: [],
      },
    })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('暂无待办')
    expect(wrapper.text()).toContain('暂无公告')
    expect(wrapper.text()).toContain('暂无课程')
    expect(wrapper.text()).toContain('暂无反馈')
  })
})
