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
const academicsMock = vi.hoisted(() => ({ listTerms: vi.fn() }))

vi.mock('../../../api/dashboard.js', () => ({ dashboardAPI: studentMock }))
vi.mock('../../../api/announcements.js', () => ({ announcementsAPI: markReadMock }))
vi.mock('../../../api/courses.js', () => ({ coursesAPI: coursesMock }))
vi.mock('../../../api/progress.js', () => ({ progressAPI: progressMock }))
vi.mock('../../../api/academics.js', () => ({ academicsAPI: academicsMock }))

import DashboardView from '../DashboardView.vue'

const makeAnnouncement = (id, overrides = {}) => ({
  id,
  title: `公告${id}`,
  content: `公告${id}的正文`,
  priority: id === 9 ? 'important' : 'normal',
  scope: 'course',
  course_id: 2,
  course_title: '机器学习导论',
  author_name: '王老师',
  published_at: '2026-08-01T04:00:00Z',
  expires_at: null,
  is_read: id !== 9,
  ...overrides,
})

const dashboardData = () => ({
  student_no: '20260001',
  teaching_classes: ['智科一班'],
  summary: {
    course_count: 4,
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
    {
      kind: 'exam',
      id: 5,
      title: '阶段测试',
      course_title: '程序设计基础',
      time_at: '2026-08-03T01:00:00Z',
      urgency: 'soon',
      route: '/student/exams/5',
    },
    {
      kind: 'experiment',
      id: 6,
      title: '数据清洗实验',
      course_title: '数据科学实践',
      time_at: '2026-08-01T01:00:00Z',
      urgency: 'normal',
      route: '/student/experiments/6',
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
      academic_term: '2026—2027 学年第一学期（秋季）',
      teaching_classes: ['智科一班'],
      pending_assignment_count: 1,
      upcoming_exam_count: 1,
      last_activity_at: '2026-08-01T05:10:00Z',
      route: '/student/courses/2',
    },
    {
      id: 3,
      title: '程序设计基础',
      academic_term: '2026—2027 学年第一学期（秋季）',
      teaching_classes: ['智科一班'],
      pending_assignment_count: 0,
      upcoming_exam_count: 1,
      last_activity_at: null,
      route: '/student/courses/3',
    },
    {
      id: 4,
      title: '数据科学实践',
      academic_term: '2026—2027 学年第一学期（秋季）',
      teaching_classes: [],
      pending_assignment_count: 0,
      upcoming_exam_count: 0,
      last_activity_at: null,
      route: '/student/courses/4',
    },
    {
      id: 5,
      title: '往期课程',
      academic_term: '2025—2026 学年第二学期（春季）',
      teaching_classes: [],
      pending_assignment_count: 0,
      upcoming_exam_count: 0,
      last_activity_at: null,
      route: '/student/courses/5',
    },
  ],
  recent_feedback: [],
  announcements: [
    makeAnnouncement(9, { title: '实验课机房调整', content: '本周实验课调整到 A302。', is_read: false }),
    makeAnnouncement(10),
    makeAnnouncement(11),
    makeAnnouncement(12),
  ],
})

const chaptersData = {
  items: [
    { id: 1, lessons: [
      { id: 7, title: '数据准备' },
      { id: 8, title: '模型训练' },
      { id: 9, title: '综合实践' },
    ] },
  ],
}

const progressData = {
  course_id: 2,
  total: 3,
  completed: 1,
  percent: 33,
  next_lesson_id: 8,
  items: [
    { lesson_id: 7, status: 'completed' },
    { lesson_id: 8, status: 'in_progress' },
    { lesson_id: 9, status: 'not_started' },
  ],
}

const academicTermsData = {
  items: [
    {
      id: 2,
      name: '2026—2027 学年第一学期（秋季）',
      start_date: '2026-08-01',
      end_date: '2027-01-31',
      status: 'active',
    },
    {
      id: 1,
      name: '2025—2026 学年第二学期（春季）',
      start_date: '2026-02-01',
      end_date: '2026-07-31',
      status: 'closed',
    },
  ],
}

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().setUser({ id: 1, username: 'stu', real_name: '张同学', role: 'student' })
  return mount(DashboardView, {
    global: {
      plugins: [pinia],
      stubs: {
        AppLayout: {
          props: ['variant', 'studentContext'],
          template: '<main :data-variant="variant" :data-student-class="studentContext?.className" :data-student-term="studentContext?.currentTerm"><slot /></main>',
        },
      },
    },
  })
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  studentMock.student.mockResolvedValue({ data: dashboardData() })
  markReadMock.markRead.mockResolvedValue({})
  coursesMock.getChapters.mockResolvedValue({ data: chaptersData })
  progressMock.getCourse.mockResolvedValue({ data: progressData })
  academicsMock.listTerms.mockResolvedValue({ data: academicTermsData })
})

describe('学生工作台（student workspace redesign）', () => {
  it('挂载时仅请求一次聚合数据并启用学生工作台专属外壳', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(studentMock.student).toHaveBeenCalledTimes(1)
    expect(academicsMock.listTerms).toHaveBeenCalledWith({ page: 1, page_size: 100 })
    expect(wrapper.get('main').attributes('data-variant')).toBe('student-workspace')
    expect(wrapper.get('main').attributes('data-student-class')).toBe('智科一班')
    expect(wrapper.get('main').attributes('data-student-term')).toBe('2026—2027 学年第一学期（秋季）')
  })

  it('按设计稿顺序渲染欢迎区、学期概览、学习工作区和课程区', async () => {
    const wrapper = mountView()
    await flushPromises()
    const order = wrapper.findAll('.student-dashboard > *').map((node) => node.classes())
    expect(order[0]).toContain('welcome-section')
    expect(order[1]).toContain('semester-overview')
    expect(order[2]).toContain('learning-workspace')
    expect(order[3]).toContain('course-section')
    expect(wrapper.find('.feedback-panel').exists()).toBe(false)
    const main = wrapper.findAll('.main-column > *').map((node) => node.classes())
    const side = wrapper.findAll('.side-column > *').map((node) => node.classes())
    expect(main[0]).toContain('today-focus-card')
    expect(main[1]).toContain('task-card')
    expect(side[0]).toContain('schedule-card')
    expect(side[1]).toContain('announcement-card')
  })

  it('欢迎区显示真实姓名、日期、引导语和只读的当前学期', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.get('.greeting-title').text()).toContain('张同学')
    expect(wrapper.get('.greeting-date').text()).toMatch(/年.*月.*日/)
    expect(wrapper.get('.welcome-copy').text()).toContain('先完成今天最重要的一件事')
    expect(wrapper.find('select').exists()).toBe(false)
    expect(wrapper.get('.term-display').attributes('aria-label')).toBe('当前学期')
    expect(wrapper.get('.term-label').text()).toBe('当前学期')
    expect(wrapper.get('.term-value').text()).toBe('2026—2027 学年第一学期（秋季）')
  })

  it('历史课程排在前面时仍按教务 active 状态识别并展示当前学期', async () => {
    const data = dashboardData()
    const currentName = academicTermsData.items[0].name
    const historicalName = academicTermsData.items[1].name
    data.courses = [
      { ...data.courses[3], title: '历史课程', academic_term: historicalName },
      { ...data.courses[0], title: '当前课程', academic_term: ` ${currentName} ` },
    ]
    studentMock.student.mockResolvedValue({ data })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.get('.term-value').text()).toBe(currentName)
    expect(wrapper.get('.course-section').text()).toContain('当前课程')
    expect(wrapper.get('.course-section').text()).not.toContain('历史课程')
  })

  it('没有课程时仍显示教务系统中的当前学期', async () => {
    const data = dashboardData()
    data.courses = []
    studentMock.student.mockResolvedValue({ data })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.get('.term-value').text()).toBe(academicTermsData.items[0].name)
    expect(wrapper.text()).toContain('暂无课程')
  })

  it('学期接口失败时不阻断工作台数据，并如实显示学期信息不可用', async () => {
    academicsMock.listTerms.mockRejectedValue(new Error('terms unavailable'))

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.get('.term-value').text()).toBe('暂无学期信息')
    expect(wrapper.text()).toContain('特征工程')
  })

  it('复合教学班名称在侧栏上下文和课程卡中只展示清晰班号', async () => {
    const data = dashboardData()
    const compositeClass = '2026—2027 学年第一学期（秋季） 24621601班'
    data.teaching_classes = [compositeClass]
    data.courses[0].teaching_classes = [compositeClass]
    studentMock.student.mockResolvedValue({ data })
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.get('main').attributes('data-student-class')).toBe('24621601班')
    expect(wrapper.findAll('.course-card')[0].get('.course-meta').text()).toBe(
      '24621601班 · 2026—2027 学年第一学期（秋季）',
    )
  })

  it('今日重点使用真实课程与学习记录，并用章节和进度生成三步学习路径', async () => {
    const wrapper = mountView()
    await flushPromises()
    const focus = wrapper.get('.today-focus-card')
    expect(focus.get('.focus-title').text()).toBe('机器学习导论')
    expect(focus.get('.focus-meta').text()).toContain('学习记录 · 决策树实验')
    expect(focus.get('.focus-meta').text()).toContain('33%')
    expect(coursesMock.getChapters).toHaveBeenCalledWith(2)
    expect(progressMock.getCourse).toHaveBeenCalledWith(2)
    const steps = focus.findAll('.learning-step')
    expect(steps).toHaveLength(3)
    expect(steps.map((step) => step.get('.step-title').text())).toEqual(['数据准备', '模型训练', '综合实践'])
    expect(steps[0].classes()).toContain('is-completed')
    expect(steps[1].classes()).toContain('is-current')
  })

  it('继续学习和待办行只接受 /student 范围内的服务端路由', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.continue-btn').trigger('click')
    await wrapper.get('.task-row').trigger('click')
    expect(routerState.push).toHaveBeenNthCalledWith(1, '/student/courses/2/notebook/8')
    expect(routerState.push).toHaveBeenNthCalledWith(2, '/student/assignments/4')
    routerState.push.mockClear()
    studentMock.student.mockResolvedValue({
      data: {
        ...dashboardData(),
        continue_learning: { ...dashboardData().continue_learning, route: 'https://evil.example' },
        priority_items: [{ ...dashboardData().priority_items[0], route: '//evil.example' }],
      },
    })
    const unsafeWrapper = mountView()
    await flushPromises()
    await unsafeWrapper.get('.continue-btn').trigger('click')
    await unsafeWrapper.get('.task-row').trigger('click')
    expect(routerState.push).not.toHaveBeenCalled()
  })

  it('四项概览展示真实计数和目标文案', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.findAll('.summary-num').map((node) => node.text())).toEqual(['4', '1', '1', '2'])
    expect(wrapper.findAll('.summary-label').map((node) => node.text())).toEqual([
      '已加入课程', '待交作业', '即将考试', '未读公告',
    ])
  })

  it('待办任务支持全部、作业、考试筛选并同步 aria-pressed', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.findAll('.task-row')).toHaveLength(3)
    const assignment = wrapper.get('[data-filter="assignment"]')
    const exam = wrapper.get('[data-filter="exam"]')
    await assignment.trigger('click')
    expect(assignment.attributes('aria-pressed')).toBe('true')
    expect(wrapper.findAll('.task-row')).toHaveLength(1)
    expect(wrapper.get('.task-row').text()).toContain('特征工程')
    await exam.trigger('click')
    expect(exam.attributes('aria-pressed')).toBe('true')
    expect(assignment.attributes('aria-pressed')).toBe('false')
    expect(wrapper.findAll('.task-row')).toHaveLength(1)
    expect(wrapper.get('.task-row').text()).toContain('阶段测试')
  })

  it('学习日程仅使用带有效时间的作业和考试，并按时间排序', async () => {
    const data = dashboardData()
    data.priority_items.push({
      kind: 'assignment', id: 20, title: '无日期作业', course_title: '课程', time_at: null,
      urgency: 'normal', route: '/student/assignments/20',
    })
    studentMock.student.mockResolvedValue({ data })
    const wrapper = mountView()
    await flushPromises()
    const schedule = wrapper.findAll('.schedule-item')
    expect(schedule).toHaveLength(2)
    expect(schedule[0].text()).toContain('特征工程')
    expect(schedule[1].text()).toContain('阶段测试')
    expect(wrapper.get('.schedule-card').text()).not.toContain('数据清洗实验')
    expect(wrapper.get('.schedule-card').text()).not.toContain('无日期作业')
    expect(wrapper.get('.schedule-note').text()).toContain('今天没有截止任务')
  })

  it('独立实验没有课程章节时，用真实反馈和当前记录补齐近期学习轨迹', async () => {
    const data = dashboardData()
    data.continue_learning = {
      kind: 'module_experiment',
      title: '独立实验记录',
      subtitle: null,
      updated_at: '2026-08-19T04:18:00Z',
      route: '/student/experiments/12',
    }
    data.recent_feedback = [
      { id: 31, title: '函数练习反馈', score: 97, feedback: '结构清晰' },
      { id: 30, title: '字典练习反馈', score: 88, feedback: null },
    ]
    studentMock.student.mockResolvedValue({ data })
    const wrapper = mountView()
    await flushPromises()

    expect(coursesMock.getChapters).not.toHaveBeenCalled()
    expect(progressMock.getCourse).not.toHaveBeenCalled()
    const steps = wrapper.findAll('.learning-step')
    expect(steps).toHaveLength(3)
    expect(steps.map((step) => step.get('.step-title').text())).toEqual([
      '字典练习反馈', '函数练习反馈', '独立实验记录',
    ])
    expect(steps[2].classes()).toContain('is-current')
  })

  it('公告最多显示三条，标记已读后只将未读数安全减一', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.findAll('.announcement-item')).toHaveLength(3)
    expect(wrapper.get('.announcement-card').text()).toContain('实验课机房调整')
    expect(wrapper.get('.announcement-card').text()).not.toContain('公告12')
    expect(wrapper.findAll('.summary-num')[3].text()).toBe('2')
    await wrapper.get('.mark-read-btn').trigger('click')
    await flushPromises()
    expect(markReadMock.markRead).toHaveBeenCalledWith(9)
    expect(wrapper.find('.mark-read-btn').exists()).toBe(false)
    expect(wrapper.findAll('.summary-num')[3].text()).toBe('1')
  })

  it('课程区最多三张真实课程卡，并支持课程和查看全部跳转', async () => {
    const wrapper = mountView()
    await flushPromises()
    const cards = wrapper.findAll('.course-card')
    expect(cards).toHaveLength(3)
    expect(cards[0].text()).toContain('机器学习导论')
    expect(cards[0].text()).toContain('智科一班')
    expect(cards[0].text()).toContain('1 份待交')
    expect(wrapper.get('.course-section').text()).not.toContain('往期课程')
    await cards[0].trigger('click')
    await wrapper.get('.all-courses-btn').trigger('click')
    expect(routerState.push).toHaveBeenNthCalledWith(1, '/student/courses/2')
    expect(routerState.push).toHaveBeenNthCalledWith(2, '/student/courses')
  })

  it('聚合请求失败显示错误并可重试', async () => {
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

  it('全空数据展示真实空态，不出现反馈区或虚构业务数据', async () => {
    studentMock.student.mockResolvedValue({
      data: {
        student_no: null,
        teaching_classes: [],
        summary: { course_count: 0, pending_assignment_count: 0, upcoming_exam_count: 0, unread_announcement_count: 0 },
        priority_items: [],
        continue_learning: null,
        courses: [],
        recent_feedback: [],
        announcements: [],
      },
    })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('暂无学习记录')
    expect(wrapper.text()).toContain('暂无待办')
    expect(wrapper.text()).toContain('暂无日程')
    expect(wrapper.text()).toContain('暂无公告')
    expect(wrapper.text()).toContain('暂无课程')
    expect(wrapper.find('.feedback-panel').exists()).toBe(false)
    expect(wrapper.text()).not.toMatch(/\d+%/)
  })

  it('章节或进度辅助请求失败时仍显示重点卡，但不伪造路径或百分比', async () => {
    coursesMock.getChapters.mockRejectedValue(new Error('chapters unavailable'))
    progressMock.getCourse.mockRejectedValue(new Error('progress unavailable'))
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.get('.today-focus-card').text()).toContain('机器学习导论')
    expect(wrapper.findAll('.learning-step')).toHaveLength(0)
    expect(wrapper.get('.today-focus-card').text()).not.toMatch(/\d+%/)
  })

  it('源码不含设计稿中的样例业务数据', () => {
    const here = dirname(fileURLToPath(import.meta.url))
    const source = readFileSync(resolve(here, '../DashboardView.vue'), 'utf-8')
    for (const sample of ['林书瑶', '12111', 'Python 与 AI 实验全流程', '统计练习：均值与方差']) {
      expect(source).not.toContain(sample)
    }
  })

  it('沿用全局字体与收紧的圆角 token，不再保留设计稿的独立大圆角', () => {
    const here = dirname(fileURLToPath(import.meta.url))
    const source = readFileSync(resolve(here, '../DashboardView.vue'), 'utf-8')

    expect(source).not.toMatch(/--(?:display|body|mono)-font:/)
    expect(source).not.toMatch(/border-radius:\s*(?:8|9|10|16)px/)
    expect(source).toContain('font-family: var(--font-body);')
    expect(source).toContain('border-radius: var(--radius-lg);')
    expect(source).toContain('border-radius: var(--radius-md);')
  })
})
