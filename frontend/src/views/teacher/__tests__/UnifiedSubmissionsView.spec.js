import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const routerState = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: routerState.push }),
}))

const unifiedMock = vi.hoisted(() => ({ unified: vi.fn() }))
vi.mock('../../../api/submissions.js', () => ({ submissionsAPI: unifiedMock }))

import UnifiedSubmissionsView from '../UnifiedSubmissionsView.vue'

const response = {
  items: [
    {
      kind: 'assignment', id: 11, student_name: '陈雨桐', student_no: '2026011203',
      entry_title: '特征工程 · 题一', course_title: '机器学习基础',
      status: 'pending_grading', status_tone: 'warning',
      tests_passed: null, tests_total: null, ai_score: null, score: null,
      submitted_at: '2026-08-14T18:32:00Z', route: '/teacher/judge-submissions/11',
    },
  ],
  page: 1,
  page_size: 10,
  total: 1,
  summary: { total: 1, pending: 1, graded: 0, review: 0, failed: 0 },
  filter_options: { courses: [], entries: [] },
}

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(UnifiedSubmissionsView, {
    global: {
      plugins: [pinia],
      stubs: { AppLayout: { template: '<main><slot /></main>' } },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  unifiedMock.unified.mockResolvedValue({ data: response })
})

describe('统一提交中心 UnifiedSubmissionsView', () => {
  it('挂载时加载统一提交列表', async () => {
    mountView()
    await flushPromises()
    expect(unifiedMock.unified).toHaveBeenCalledTimes(1)
    expect(unifiedMock.unified.mock.calls[0][0].kind).toBe('all')
  })

  it('展示学生、任务与状态徽标', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('陈雨桐')
    expect(wrapper.text()).toContain('2026011203')
    expect(wrapper.text()).toContain('特征工程 · 题一')
    expect(wrapper.text()).toContain('待评分')
  })

  it('点击行跳转到详情路由', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.get('tbody tr').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/teacher/judge-submissions/11')
  })
})
