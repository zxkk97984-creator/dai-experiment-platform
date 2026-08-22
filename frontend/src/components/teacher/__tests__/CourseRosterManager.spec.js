import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const showToastMock = vi.hoisted(() => vi.fn())

vi.mock('../../../api/courses.js', () => ({
  coursesAPI: {
    listStudents: vi.fn(),
    addStudent: vi.fn(),
    removeStudent: vi.fn(),
    importStudents: vi.fn(),
  },
}))
vi.mock('../../../api/users.js', () => ({ usersAPI: { listStudents: vi.fn() } }))
vi.mock('../../../stores/app.js', () => ({
  useAppStore: () => ({ showToast: showToastMock }),
}))

import { coursesAPI } from '../../../api/courses.js'
import CourseRosterManager from '../CourseRosterManager.vue'

const student = { id: 11, username: 'student-11', student_no: '20260011', real_name: '学生十一' }

describe('课程名单管理器', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    coursesAPI.listStudents.mockResolvedValue({ data: { items: [student], total: 101 } })
  })

  it('使用后端 total 分页而不是固定取前 100 人', async () => {
    const wrapper = mount(CourseRosterManager, {
      props: { courseId: 88 },
      global: { stubs: { AppIcon: { template: '<span />' } } },
    })
    await flushPromises()

    expect(coursesAPI.listStudents).toHaveBeenCalledWith(88, { page: 1, page_size: 20 })
    const next = wrapper.find('[aria-label="课程名单分页"] button[aria-label="下一页"]')
    expect(next.exists()).toBe(true)
    await next.trigger('click')
    await flushPromises()
    expect(coursesAPI.listStudents).toHaveBeenLastCalledWith(88, { page: 2, page_size: 20 })
  })
})
