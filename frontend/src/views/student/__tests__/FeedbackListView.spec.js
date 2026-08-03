// 提交与反馈（参考图 01）：recent_feedback 列表 + 状态标签 + 组合筛选 + 分页页脚
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
    useRoute: () => ({ path: '/student/feedback' }),
  }
})

const dashboardMock = vi.hoisted(() => ({ student: vi.fn() }))
vi.mock('../../../api/dashboard.js', () => ({ dashboardAPI: dashboardMock }))

import FeedbackListView from '../FeedbackListView.vue'

const DAY = 86400000
const recent = (offsetDays) => new Date(Date.now() - offsetDays * DAY).toISOString()

function feedbackData() {
  return {
    data: {
      summary: { course_count: 2, pending_assignment_count: 0, upcoming_exam_count: 0, unread_announcement_count: 0 },
      priority_items: [],
      continue_learning: null,
      courses: [],
      recent_feedback: [
        { kind: 'assignment', id: 1, title: '线性回归作业', course_title: '机器学习导论', score: 88, feedback: '推导清晰', graded_at: recent(1), route: '/student/submissions/11' },
        { kind: 'assignment', id: 2, title: '决策树作业', course_title: '机器学习导论', score: 45, feedback: '需补充实验分析', graded_at: recent(2), route: '/student/submissions/12' },
        { kind: 'experiment', id: 3, title: '实验反馈', course_title: '数据结构', score: null, feedback: '等待评分', graded_at: recent(3), route: '/student/experiments/7' },
        { kind: 'exam', id: 4, title: '期中考试', course_title: '数据结构', score: 92, feedback: '表现优秀', graded_at: recent(4), route: '/student/submissions/13' },
      ],
      announcements: [],
    },
  }
}

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().setUser({ id: 1, username: 'stu', real_name: '测试生', role: 'student' })
  return mount(FeedbackListView, {
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

describe('提交与反馈 FeedbackListView（参考图 01）', () => {
  it('渲染聚合数据为反馈列表', async () => {
    dashboardMock.student.mockResolvedValue(feedbackData())
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.get('.page-title').text()).toContain('反馈')
    expect(wrapper.text()).toContain('线性回归作业')
    expect(wrapper.text()).toContain('88')
    expect(wrapper.text()).toContain('推导清晰')
  })

  it('状态标签：全部/需修改/已通过/等待评分 按计算状态过滤', async () => {
    dashboardMock.student.mockResolvedValue(feedbackData())
    const wrapper = mountView()
    await flushPromises()
    const tabs = wrapper.findAll('.status-tab').map((t) => t.text())
    expect(tabs[0]).toContain('全部')
    expect(tabs[1]).toContain('需修改')
    expect(tabs[2]).toContain('已通过')
    expect(tabs[3]).toContain('等待评分')

    await wrapper.findAll('.status-tab')[1].trigger('click')
    expect(wrapper.findAll('.feedback-row').length).toBe(1)
    expect(wrapper.text()).toContain('决策树作业')

    await wrapper.findAll('.status-tab')[2].trigger('click')
    expect(wrapper.findAll('.feedback-row').length).toBe(2)

    await wrapper.findAll('.status-tab')[3].trigger('click')
    expect(wrapper.findAll('.feedback-row').length).toBe(1)
    expect(wrapper.text()).toContain('实验反馈')
  })

  it('课程与搜索组合过滤', async () => {
    dashboardMock.student.mockResolvedValue(feedbackData())
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.filter-course').setValue('机器学习导论')
    expect(wrapper.findAll('.feedback-row').length).toBe(2)
    await wrapper.get('.search-input').setValue('决策')
    expect(wrapper.findAll('.feedback-row').length).toBe(1)
  })

  it('查看详情仅接受安全 /student 路由', async () => {
    dashboardMock.student.mockResolvedValue(feedbackData())
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('.detail-link')[0].trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student/submissions/11')

    // 服务端返回非 /student 路由时拒绝跳转
    dashboardMock.student.mockResolvedValue({
      data: {
        ...feedbackData().data,
        recent_feedback: [{ ...feedbackData().data.recent_feedback[0], route: 'https://evil.example/x' }],
      },
    })
    const wrapper2 = mountView()
    await flushPromises()
    await wrapper2.get('.detail-link').trigger('click')
    expect(routerState.push).not.toHaveBeenCalledWith('https://evil.example/x')
  })

  it('分页页脚可见且一页时也连贯', async () => {
    const many = Array.from({ length: 12 }, (_, i) => ({
      kind: 'assignment',
      id: i + 1,
      title: `作业${i + 1}`,
      course_title: '机器学习导论',
      score: 60 + i,
      feedback: '评语',
      graded_at: recent(i + 1),
      route: `/student/submissions/${i + 1}`,
    }))
    dashboardMock.student.mockResolvedValue({ data: { ...feedbackData().data, recent_feedback: many } })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.get('.page-footer').exists()).toBe(true)
    expect(wrapper.text()).toContain('1 / 2')
    expect(wrapper.findAll('.feedback-row').length).toBe(10)
    await wrapper.get('.next-page').trigger('click')
    expect(wrapper.findAll('.feedback-row').length).toBe(2)
    expect(wrapper.text()).toContain('2 / 2')
  })

  it('每页条数选择器生效', async () => {
    const many = Array.from({ length: 12 }, (_, i) => ({
      kind: 'assignment',
      id: i + 1,
      title: `作业${i + 1}`,
      course_title: '机器学习导论',
      score: 60 + i,
      feedback: '评语',
      graded_at: recent(i + 1),
      route: `/student/submissions/${i + 1}`,
    }))
    dashboardMock.student.mockResolvedValue({ data: { ...feedbackData().data, recent_feedback: many } })
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('.page-size').setValue('20')
    expect(wrapper.findAll('.feedback-row').length).toBe(12)
  })

  it('空数据展示如实空态', async () => {
    dashboardMock.student.mockResolvedValue({ data: { ...feedbackData().data, recent_feedback: [] } })
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('暂无反馈')
  })

  it('请求失败展示错误并可重试', async () => {
    dashboardMock.student
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce(feedbackData())
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('加载失败')
    await wrapper.get('.retry-btn').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('线性回归作业')
  })
})
