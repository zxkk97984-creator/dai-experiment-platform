import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const pushMock = vi.hoisted(() => vi.fn())
const showToastMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('../../../api/users.js', () => ({
  usersAPI: { list: vi.fn(), updateStatus: vi.fn() },
}))

vi.mock('../../../stores/app.js', () => ({
  useAppStore: () => ({ showToast: showToastMock }),
}))

import { usersAPI } from '../../../api/users.js'
import UserListView from '../UserListView.vue'

const users = [
  { id: 1, username: 'student-one', student_no: '20260001', real_name: '张三', role: 'student', status: 'active' },
]

async function mountPage() {
  const wrapper = mount(UserListView, {
    global: {
      stubs: {
        AppLayout: { template: '<div><slot /></div>' },
        AppIcon: { template: '<svg />' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('管理员用户列表搜索', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    usersAPI.list.mockResolvedValue({ data: { items: users, total: users.length } })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('按用户名、学号或姓名搜索，并向接口传递去空格后的关键词', async () => {
    vi.useFakeTimers()
    const wrapper = await mountPage()
    usersAPI.list.mockClear()

    const input = wrapper.get('input[aria-label="搜索用户名、学号或姓名"]')
    await input.setValue(' 20260001 ')
    await vi.advanceTimersByTimeAsync(250)
    await flushPromises()

    expect(usersAPI.list).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 20,
      q: '20260001',
      role: undefined,
      status_filter: undefined,
    })
  })

  it('清空关键词后重新加载全部用户', async () => {
    vi.useFakeTimers()
    const wrapper = await mountPage()
    const input = wrapper.get('input[aria-label="搜索用户名、学号或姓名"]')
    await input.setValue('张三')
    await vi.advanceTimersByTimeAsync(250)
    await flushPromises()
    usersAPI.list.mockClear()

    await wrapper.get('button[aria-label="清空搜索"]').trigger('click')
    await vi.advanceTimersByTimeAsync(250)
    await flushPromises()

    expect(usersAPI.list).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 20,
      q: undefined,
      role: undefined,
      status_filter: undefined,
    })
  })
})
