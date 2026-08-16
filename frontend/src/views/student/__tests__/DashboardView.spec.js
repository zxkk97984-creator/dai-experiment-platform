// 学生首页：参考图 04 构成——问候 → 续学面板 → 四摘要卡 → 左列(待办|反馈) → 右列(学习概览|公告|我的课程)
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

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
const coursesMock = vi.hoisted(() => ({ getChapters: vi.fn() }))
const progressMock = vi.hoisted(() => ({ getCourse: vi.fn() }))

vi.mock('../../../api/dashboard.js', () => ({ dashboardAPI: studentMock }))
vi.mock('../../../api/announcements.js', () => ({ announcementsAPI: markReadMock }))
vi.mock('../../../api/courses.js', () => ({ coursesAPI: coursesMock }))
vi.mock('../../../api/progress.js', () => ({ progressAPI: progressMock }))

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

// 课程 2 有两个课时，本地完成 1 个 → 50%
const chaptersData = { items: [{ id: 1, lessons: [{ id: 8 }, { id: 9 }] }] }

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
  coursesMock.getChapters.mockReset()
  progressMock.getCourse.mockReset()
})

describe('学生首页 DashboardView（参考图 04 构成）', () => {
  it('挂载时请求一次聚合数据', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersData })
    mountView()
    await flushPromises()
    expect(studentMock.student).toHaveBeenCalledTimes(1)
  })

  it('渲染顺序：问候 → 续学面板 → 四摘要卡 → 双列 → 我的课程通栏', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersData })
    const wrapper = mountView()
    await flushPromises()
    const order = wrapper.findAll('.dash > *').map((n) => n.classes().join(' '))
    expect(order[0]).toMatch(/greeting/)
    expect(order[1]).toMatch(/continue-panel/)
    expect(order[2]).toMatch(/summary-cards/)
    expect(order[3]).toMatch(/dash-grid/)
    expect(order[4]).toMatch(/courses-panel/)
  })

  it('双列内部顺序：左列待办→反馈；右列学习概览→公告；课程在双列下方通栏', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersData })
    const wrapper = mountView()
    await flushPromises()
    const left = wrapper.findAll('.col-left > *').map((n) => n.classes().join(' '))
    expect(left[0]).toMatch(/tasks-panel/)
    expect(left[1]).toMatch(/feedback-panel/)
    const right = wrapper.findAll('.col-right > *').map((n) => n.classes().join(' '))
    expect(right[0]).toMatch(/learning-panel/)
    expect(right[1]).toMatch(/announcement-panel-wrap/)
    expect(right).toHaveLength(2)
    expect(wrapper.find('.courses-panel').exists()).toBe(true)
  })

  it('问候显示姓名与格式化日期', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersData })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.get('.greeting-title').text()).toContain('张同学')
    expect(wrapper.get('.greeting-date').text()).toMatch(/月|日/)
  })

  it('续学面板展示真实课程标题、副标题与服务端进度（TASK-018）', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    progressMock.getCourse.mockResolvedValue({
      data: { course_id: 2, total: 2, completed: 1, percent: 50, next_lesson_id: 9, items: [] },
    })
    const wrapper = mountView()
    await flushPromises()
    const panel = wrapper.get('.continue-panel')
    expect(panel.text()).toContain('决策树实验')
    expect(panel.text()).toContain('机器学习导论')
    expect(panel.text()).toContain('50%')
    expect(panel.find('.ui-progress').exists()).toBe(true)
    expect(progressMock.getCourse).toHaveBeenCalledWith(2)
  })

  it('续学按钮跳转服务端路由且只接受 /student 前缀', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersData })
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.continue-btn').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/courses/2/notebook/8')
    routerState.push.mockClear()
    // 服务端返回非 /student 路由时拒绝跳转
    studentMock.student.mockResolvedValue({
      data: { ...dashboardData(), continue_learning: { ...dashboardData().continue_learning, route: 'https://evil.example' } },
    })
    const wrapper2 = mountView()
    await flushPromises()
    await wrapper2.get('.continue-btn').trigger('click')
    expect(routerState.push).not.toHaveBeenCalled()
  })

  it('四个摘要卡展示真实计数', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersData })
    const wrapper = mountView()
    await flushPromises()
    const nums = wrapper.findAll('.summary-num').map((n) => n.text())
    expect(nums).toEqual(['2', '1', '1', '2'])
    const labels = wrapper.findAll('.summary-label').map((n) => n.text())
    expect(labels).toEqual(['课程', '待交作业', '即将考试', '未读公告'])
  })

  it('待办任务最多三条并支持查看全部', async () => {
    studentMock.student.mockResolvedValue({
      data: {
        ...dashboardData(),
        priority_items: Array.from({ length: 5 }, (_, i) => ({
          kind: 'assignment', id: i, title: `任务${i}`, urgency: 'normal', route: '/student/assignments/1',
        })),
      },
    })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersData })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.findAll('.task-row').length).toBe(3)
    await wrapper.findAll('.view-all-btn')[0].trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/assignments')
  })

  it('最新反馈最多三条且“查看全部反馈”路由到 /student/feedback', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersData })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('特征选择解释清晰。')
    expect(wrapper.text()).toContain('92')
    const allBtn = wrapper.find('.feedback-panel .view-all-btn')
    await allBtn.trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/feedback')
  })

  it('课程快照跳转课程路由', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersData })
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.course-row-link').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/courses/2')
  })

  it('公告渲染且标记已读后本地更新并安全减一', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersData })
    markReadMock.markRead.mockResolvedValue({})
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('实验课机房调整')
    const nums = () => wrapper.findAll('.summary-num').map((n) => n.text())
    expect(nums()[3]).toBe('2')
    await wrapper.get('.mark-read-btn').trigger('click')
    expect(markReadMock.markRead).toHaveBeenCalledWith(9)
    await flushPromises()
    expect(wrapper.find('.mark-read-btn').exists()).toBe(false)
    expect(nums()[3]).toBe('1')
  })

  it('请求失败展示错误并可重试', async () => {
    studentMock.student
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ data: dashboardData() })
    coursesMock.getChapters.mockResolvedValue({ data: chaptersData })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('加载失败')
    await wrapper.get('.retry-btn').trigger('click')
    await flushPromises()
    expect(studentMock.student).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('特征工程')
  })

  it('空数据展示如实空态，不渲染假数字', async () => {
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
    // 不渲染虚构数字
    expect(wrapper.text()).not.toContain('78%')
    expect(wrapper.text()).not.toContain('6 门')
  })

  it('续学章节请求失败时页面不报错，进度不伪造', async () => {
    studentMock.student.mockResolvedValue({ data: dashboardData() })
    coursesMock.getChapters.mockRejectedValue(new Error('boom'))
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('.continue-panel').exists()).toBe(true)
    // 进度不可用时不渲染伪造百分比
    expect(wrapper.text()).not.toMatch(/\d+%/)
  })

  it('源码不含参考图样例姓名与数字', () => {
    const here = dirname(fileURLToPath(import.meta.url))
    const source = readFileSync(resolve(here, '../DashboardView.vue'), 'utf-8')
    for (const sample of ['爱丽丝', '张老师', '张教授', '机器学习导论']) {
      expect(source).not.toContain(sample)
    }
  })
})
