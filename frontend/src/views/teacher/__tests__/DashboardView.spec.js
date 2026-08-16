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
    useRoute: () => ({ path: '/teacher' }),
  }
})

const teacherMock = vi.hoisted(() => ({ teacher: vi.fn() }))
const announcementsMock = vi.hoisted(() => ({ create: vi.fn(), markRead: vi.fn() }))

vi.mock('../../../api/dashboard.js', () => ({ dashboardAPI: teacherMock }))
vi.mock('../../../api/announcements.js', () => ({ announcementsAPI: announcementsMock }))

import DashboardView from '../DashboardView.vue'

const dashboardData = (overrides = {}) => ({
  summary: {
    course_count: 2,
    active_course_count: 2,
    student_count: 46,
    pending_grading_count: 7,
    pending_review_count: 3,
    upcoming_deadline_count: 3,
    pending_release_count: 0,
  },
  work_items: [
    {
      kind: 'experiment_review',
      id: 21,
      title: '决策树实验 · 1 份提交待评分',
      course_id: 2,
      course_title: '机器学习导论',
      detail: '等待教师反馈',
      count: 1,
      status: 'pending_grading',
      time_at: '2026-08-01T05:40:00Z',
      urgency: 'soon',
      route: '/teacher/submissions/21',
    },
  ],
  course_health: [
    {
      course_id: 2,
      title: '机器学习导论',
      student_count: 24,
      pending_review_count: 3,
      upcoming_deadline_count: 1,
      at_risk_submitted_count: 18,
      at_risk_expected_count: 24,
      route: '/teacher/courses/2/manage',
    },
  ],
  recent_activity: [
    {
      kind: 'experiment_submission',
      id: 21,
      title: '张同学提交了决策树实验',
      course_title: '机器学习导论',
      actor_name: '张同学',
      happened_at: '2026-08-01T05:40:00Z',
      route: '/teacher/submissions/21',
    },
  ],
  recent_submissions: [
    {
      kind: 'experiment',
      id: 21,
      student_name: '张同学',
      student_no: '2026011201',
      entry_title: '决策树实验',
      course_id: 2,
      course_title: '机器学习导论',
      status: 'pending_grading',
      status_tone: 'warning',
      tests_passed: null,
      tests_total: null,
      ai_score: null,
      score: null,
      submitted_at: '2026-08-01T05:40:00Z',
      route: '/teacher/submissions/21',
    },
  ],
  managed_courses: [{ id: 2, title: '机器学习导论' }],
  announcements: [],
  ...overrides,
})

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().setUser({ id: 1, username: 'teacher', real_name: '王老师', role: 'teacher' })
  return mount(DashboardView, {
    global: {
      plugins: [pinia],
      stubs: { AppLayout: { template: '<main><slot /></main>' } },
    },
    // attachTo document.body：焦点恢复断言需要组件在 jsdom DOM 中
    attachTo: document.body,
  })
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  teacherMock.teacher.mockReset()
  announcementsMock.create.mockReset()
  announcementsMock.markRead.mockReset()
})

describe('教师首页 DashboardView', () => {
  it('挂载时请求一次聚合数据', async () => {
    teacherMock.teacher.mockResolvedValue({ data: dashboardData() })
    mountView()
    await flushPromises()
    expect(teacherMock.teacher).toHaveBeenCalledTimes(1)
  })

  it('展示真实摘要与工作队列，旧硬编码时间线消失', async () => {
    teacherMock.teacher.mockResolvedValue({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('待评分')
    expect(wrapper.text()).toContain('近 7 天截止')
    expect(wrapper.text()).toContain('决策树实验 · 1 份提交待评分')
    expect(wrapper.text()).toContain('待评分')
    expect(wrapper.text()).not.toContain('12 份待批改')
    expect(wrapper.text()).not.toContain('平均用时')
  })

  it('工作队列主按钮跳转第一个工作项', async () => {
    teacherMock.teacher.mockResolvedValue({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.work-queue-btn').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/teacher/submissions/21')
  })

  it('课程概览展示分母式提交数与跳转', async () => {
    teacherMock.teacher.mockResolvedValue({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('18/24 已提交')
    await wrapper.get('.health-link').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/teacher/courses/2/manage')
  })

  it('最近提交表格来自真实提交', async () => {
    teacherMock.teacher.mockResolvedValue({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('最近提交')
    expect(wrapper.text()).toContain('张同学')
    expect(wrapper.text()).toContain('2026011201')
  })

  it('发布公告：提交精确 payload 后视图刷新并展示新公告', async () => {
    const newNotice = {
      id: 99,
      title: '机房调整',
      content: '本周实验课调整到 A302。',
      priority: 'normal',
      scope: 'course',
      course_id: 2,
      course_title: '机器学习导论',
      author_name: '王老师',
      published_at: '2026-08-01T06:00:00Z',
      expires_at: null,
      is_read: false,
    }
    teacherMock.teacher
      .mockResolvedValueOnce({ data: dashboardData() })
      .mockResolvedValueOnce({ data: dashboardData({ announcements: [newNotice] }) })
    announcementsMock.create.mockResolvedValue({ data: newNotice })

    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.publish-btn').trigger('click')
    await wrapper.get('.composer-form input[type="text"]').setValue('机房调整')
    await wrapper.get('.composer-form textarea').setValue('本周实验课调整到 A302。')
    // jsdom 中点击 submit 按钮不会派发表单提交事件，直接触发表单 submit
    await wrapper.get('.composer-form').trigger('submit')
    await flushPromises()

    expect(announcementsMock.create).toHaveBeenCalledTimes(1)
    expect(announcementsMock.create).toHaveBeenCalledWith({
      title: '机房调整',
      content: '本周实验课调整到 A302。',
      priority: 'normal',
      scope: 'course',
      course_id: 2,
    })
    // 发布成功后重新拉取聚合数据
    expect(teacherMock.teacher).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('机房调整')
    // 发布成功后焦点恢复到发布按钮
    expect(document.activeElement?.classList.contains('publish-btn')).toBe(true)
  })

  it('教师可标记公告已读并本地更新', async () => {
    const notice = {
      id: 7,
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
    }
    teacherMock.teacher.mockResolvedValue({ data: dashboardData({ announcements: [notice] }) })
    announcementsMock.markRead.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('.mark-read-btn').exists()).toBe(true)
    await wrapper.get('.mark-read-btn').trigger('click')
    expect(announcementsMock.markRead).toHaveBeenCalledWith(7)
    await flushPromises()
    expect(wrapper.find('.mark-read-btn').exists()).toBe(false)
  })

  it('关闭发布模态后焦点恢复到发布按钮', async () => {
    teacherMock.teacher.mockResolvedValue({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.publish-btn').trigger('click')
    expect(wrapper.get('.composer-modal').exists()).toBe(true)
    await wrapper.get('.composer-modal').trigger('keydown', { key: 'Escape' })
    await flushPromises()
    expect(wrapper.find('.composer-modal').exists()).toBe(false)
    expect(document.activeElement?.classList.contains('publish-btn')).toBe(true)
  })

  it('请求失败展示错误并可重试', async () => {
    teacherMock.teacher
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ data: dashboardData() })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('加载失败')
    await wrapper.get('.retry-btn').trigger('click')
    await flushPromises()
    expect(teacherMock.teacher).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('决策树实验 · 1 份提交待评分')
  })

  it('空数据展示如实空态', async () => {
    teacherMock.teacher.mockResolvedValue({
      data: {
        summary: {
          course_count: 0,
          student_count: 0,
          pending_review_count: 0,
          upcoming_deadline_count: 0,
        },
        work_items: [],
        course_health: [],
        recent_activity: [],
        managed_courses: [],
        announcements: [],
      },
    })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('暂无待处理工作')
    expect(wrapper.text()).toContain('暂无课程')
    expect(wrapper.text()).toContain('暂无提交')
    expect(wrapper.text()).toContain('暂无公告')
  })
})
