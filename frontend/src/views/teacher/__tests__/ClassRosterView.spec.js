import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const showToastMock = vi.hoisted(() => vi.fn())

vi.mock('../../../api/academics.js', () => ({
  academicsAPI: {
    listClasses: vi.fn(),
    listClassStudents: vi.fn(),
  },
}))
vi.mock('../../../stores/app.js', () => ({
  useAppStore: () => ({ showToast: showToastMock }),
}))

import { academicsAPI } from '../../../api/academics.js'
import ClassRosterView from '../ClassRosterView.vue'

const teachingClass = { id: 7, code: 'CS-01', name: '一班', student_count: 101 }
const student = { id: 9, username: 'student-9', student_no: '20260009', real_name: '学生九' }

function mountPage() {
  return mount(ClassRosterView, {
    global: {
      stubs: {
        AppLayout: { template: '<div><slot /></div>' },
        AppIcon: { template: '<span />' },
      },
    },
  })
}

describe('教师班级名单页', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    academicsAPI.listClasses.mockResolvedValue({ data: { items: [teachingClass], total: 101 } })
    academicsAPI.listClassStudents.mockResolvedValue({ data: { items: [student], total: 101 } })
  })

  it('使用后端分页加载教学班和名单', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(academicsAPI.listClasses).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      scope: 'linked',
    })
    expect(academicsAPI.listClassStudents).toHaveBeenCalledWith(7, {
      page: 1,
      page_size: 20,
    })

    const next = wrapper.find('[aria-label="班级名单分页"] button[aria-label="下一页"]')
    expect(next.exists()).toBe(true)
    await next.trigger('click')
    await flushPromises()

    expect(academicsAPI.listClassStudents).toHaveBeenLastCalledWith(7, {
      page: 2,
      page_size: 20,
    })
  })

  it('学生搜索请求服务端而不是只过滤当前页', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const input = wrapper.find('input[placeholder="搜索姓名、学号或账号"]')
    await input.setValue('20260009')
    await input.trigger('keyup.enter')
    await flushPromises()

    expect(academicsAPI.listClassStudents).toHaveBeenLastCalledWith(7, {
      page: 1,
      page_size: 20,
      q: '20260009',
    })
  })
})
