// 课程白名单管理组件：加载名单/候选、debounce 搜索、添加/移除、空态与错误保留
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const coursesMock = vi.hoisted(() => ({
  listWhitelist: vi.fn(),
  addWhitelistStudent: vi.fn(),
  removeWhitelistStudent: vi.fn(),
}))
const usersMock = vi.hoisted(() => ({ listStudents: vi.fn() }))
const toastMock = vi.hoisted(() => ({ showToast: vi.fn() }))

vi.mock('../../../api/courses.js', () => ({ coursesAPI: coursesMock }))
vi.mock('../../../api/users.js', () => ({ usersAPI: usersMock }))
vi.mock('../../../stores/app.js', () => ({ useAppStore: () => toastMock }))

import CourseWhitelistManager from '../CourseWhitelistManager.vue'

const student = (id, username, realName = '') => ({
  id, username, real_name: realName || username, role: 'student', status: 'active',
})

const entry = (s) => ({ course_id: 7, student: s, created_at: '2026-08-04T08:00:00' })

const listData = (items) => ({ items, page: 1, page_size: 20, total: items.length })

function mountManager() {
  return mount(CourseWhitelistManager, {
    props: { courseId: 7 },
    global: { stubs: { AppIcon: { template: '<i />' } } },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useRealTimers()
  coursesMock.listWhitelist.mockReset()
  coursesMock.addWhitelistStudent.mockReset()
  coursesMock.removeWhitelistStudent.mockReset()
  usersMock.listStudents.mockReset()
})

describe('CourseWhitelistManager 白名单管理', () => {
  it('首次显示时加载名单与候选学生', async () => {
    coursesMock.listWhitelist.mockResolvedValue({ data: listData([entry(student(1, 'stu_a'))]) })
    usersMock.listStudents.mockResolvedValue({ data: listData([student(2, 'stu_b')]) })
    const wrapper = mountManager()
    await flushPromises()

    expect(coursesMock.listWhitelist).toHaveBeenCalledWith(7, expect.objectContaining({ page_size: 20 }))
    expect(usersMock.listStudents).toHaveBeenCalled()
    expect(wrapper.text()).toContain('1 名学生')
    expect(wrapper.text()).toContain('stu_a')
    expect(wrapper.text()).toContain('stu_b')
  })

  it('输入搜索词后 debounce 查询候选', async () => {
    vi.useFakeTimers()
    coursesMock.listWhitelist.mockResolvedValue({ data: listData([]) })
    usersMock.listStudents.mockResolvedValue({ data: listData([student(3, 'stu_c')]) })
    const wrapper = mountManager()
    await flushPromises()
    usersMock.listStudents.mockClear()

    await wrapper.get('input[type="search"]').setValue('张')
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()

    expect(usersMock.listStudents).toHaveBeenCalledWith(expect.objectContaining({ q: '张' }))
    expect(wrapper.text()).toContain('stu_c')
  })

  it('已添加学生显示“已添加”并禁用按钮', async () => {
    coursesMock.listWhitelist.mockResolvedValue({ data: listData([entry(student(1, 'stu_a'))]) })
    usersMock.listStudents.mockResolvedValue({ data: listData([student(1, 'stu_a'), student(2, 'stu_b')]) })
    const wrapper = mountManager()
    await flushPromises()

    const buttons = wrapper.findAll('.wl-item button')
    const added = buttons.find((b) => b.text() === '已添加')
    expect(added).toBeDefined()
    expect(added.attributes('disabled')).toBeDefined()
    const addBtn = buttons.find((b) => b.text() === '添加')
    expect(addBtn).toBeDefined()
  })

  it('添加成功刷新名单并更新计数', async () => {
    coursesMock.listWhitelist
      .mockResolvedValueOnce({ data: listData([]) })
      .mockResolvedValueOnce({ data: listData([entry(student(2, 'stu_b'))]) })
    usersMock.listStudents.mockResolvedValue({ data: listData([student(2, 'stu_b')]) })
    coursesMock.addWhitelistStudent.mockResolvedValue({})
    const wrapper = mountManager()
    await flushPromises()
    expect(wrapper.text()).toContain('0 名学生')

    await wrapper.get('.wl-add').trigger('click')
    await flushPromises()

    expect(coursesMock.addWhitelistStudent).toHaveBeenCalledWith(7, 2)
    expect(toastMock.showToast).toHaveBeenCalledWith('已加入白名单', 'success')
    expect(wrapper.text()).toContain('1 名学生')
  })

  it('单项 mutation 期间重复点击不会发出两次请求', async () => {
    let resolveAdd
    coursesMock.listWhitelist.mockResolvedValue({ data: listData([]) })
    usersMock.listStudents.mockResolvedValue({ data: listData([student(2, 'stu_b')]) })
    coursesMock.addWhitelistStudent.mockReturnValue(new Promise((r) => { resolveAdd = r }))
    const wrapper = mountManager()
    await flushPromises()

    const addBtn = wrapper.get('.wl-add')
    await addBtn.trigger('click')
    await addBtn.trigger('click')
    await flushPromises()
    expect(coursesMock.addWhitelistStudent).toHaveBeenCalledTimes(1)
    resolveAdd({})
    await flushPromises()
  })

  it('移除前弹确认框，确认后移除并刷新列表', async () => {
    coursesMock.listWhitelist
      .mockResolvedValueOnce({ data: listData([entry(student(1, 'stu_a'))]) })
      .mockResolvedValueOnce({ data: listData([]) })
    usersMock.listStudents.mockResolvedValue({ data: listData([]) })
    coursesMock.removeWhitelistStudent.mockResolvedValue({})
    const wrapper = mountManager()
    await flushPromises()

    await wrapper.get('.wl-remove').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('移出白名单')

    await wrapper.findAll('.confirm-actions button').find((b) => b.text() === '移出').trigger('click')
    await flushPromises()

    expect(coursesMock.removeWhitelistStudent).toHaveBeenCalledWith(7, 1)
    expect(wrapper.text()).toContain('0 名学生')
  })

  it('添加失败保留现有 UI 并显示错误', async () => {
    coursesMock.listWhitelist.mockResolvedValue({ data: listData([]) })
    usersMock.listStudents.mockResolvedValue({ data: listData([student(2, 'stu_b')]) })
    coursesMock.addWhitelistStudent.mockRejectedValue(
      Object.assign(new Error('conflict'), { response: { status: 409, data: { detail: { message: '该学生已在白名单中' } } } }),
    )
    const wrapper = mountManager()
    await flushPromises()

    await wrapper.get('.wl-add').trigger('click')
    await flushPromises()

    expect(toastMock.showToast).toHaveBeenCalledWith('该学生已在白名单中', 'error')
    // 列表未被清空，候选仍在
    expect(wrapper.text()).toContain('stu_b')
    expect(wrapper.get('.wl-add').exists()).toBe(true)
  })

  it('空名单显示风险提示', async () => {
    coursesMock.listWhitelist.mockResolvedValue({ data: listData([]) })
    usersMock.listStudents.mockResolvedValue({ data: listData([]) })
    const wrapper = mountManager()
    await flushPromises()

    expect(wrapper.text()).toContain('当前未添加学生，保存为白名单后将没有学生可以看到该课程。')
  })

  it('“加载更多”翻页追加名单', async () => {
    coursesMock.listWhitelist
      .mockResolvedValueOnce({ data: { items: [entry(student(1, 'stu_a'))], page: 1, page_size: 20, total: 21 } })
      .mockResolvedValueOnce({ data: { items: [entry(student(2, 'stu_b'))], page: 2, page_size: 20, total: 21 } })
    usersMock.listStudents.mockResolvedValue({ data: listData([]) })
    const wrapper = mountManager()
    await flushPromises()

    await wrapper.get('.wl-more').trigger('click')
    await flushPromises()

    expect(coursesMock.listWhitelist).toHaveBeenLastCalledWith(7, expect.objectContaining({ page: 2 }))
    expect(wrapper.findAll('.wl-item').length).toBe(2)
    expect(wrapper.text()).toContain('stu_b')
  })
})
