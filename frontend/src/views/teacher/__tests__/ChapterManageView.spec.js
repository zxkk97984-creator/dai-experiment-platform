/** Task 1: 课程管理页白屏修复——组件回归测试 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const push = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  useRouter: () => ({ push }),
  createRouter: vi.fn(() => ({
    beforeEach: vi.fn(),
    afterEach: vi.fn(),
    beforeResolve: vi.fn(),
    push: vi.fn(),
    replace: vi.fn(),
    currentRoute: { value: { path: '/teacher/courses/1/manage' } },
  })),
  createWebHistory: vi.fn(() => ({})),
}))

vi.mock('../../../api/courses', () => ({
  coursesAPI: {
    get: vi.fn(),
    getChapters: vi.fn(),
    createChapter: vi.fn(),
    createLesson: vi.fn(),
    updateLesson: vi.fn(),
  },
}))

vi.mock('../../../api/studio', () => ({
  studioAPI: {
    createTemplate: vi.fn(),
  },
}))

vi.mock('../../../stores/app', () => ({
  useAppStore: () => ({
    showToast: vi.fn(),
  }),
}))

import { coursesAPI } from '../../../api/courses.js'

describe('课程管理页 ChapterManageView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('加载并展示课程名、章节名和课时名', async () => {
    coursesAPI.get.mockResolvedValue({
      data: { id: 1, title: '验收课程' },
    })
    coursesAPI.getChapters.mockResolvedValue({
      data: [
        {
          id: 11,
          title: '第一章',
          order_index: 1,
          lessons: [
            { id: 111, title: '第一课', content_type: 'markdown', order_index: 1 },
          ],
        },
      ],
    })

    const mod = await import('../ChapterManageView.vue')
    const wrapper = mount(mod.default, {
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          AppLayout: { template: '<div><slot /></div>' },
        },
      },
    })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('验收课程')
    expect(text).toContain('第一章')
    expect(text).toContain('第一课')
    expect(coursesAPI.get).toHaveBeenCalledWith('1')
    expect(coursesAPI.getChapters).toHaveBeenCalledWith('1')
  })
})
