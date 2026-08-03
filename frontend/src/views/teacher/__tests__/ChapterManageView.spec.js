/** 课程管理页 ChapterManageView 组件测试：菜单功能、发布状态、删除 / 移动 / 发布切换 */
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
    updateChapter: vi.fn(),
    deleteChapter: vi.fn(),
    deleteLesson: vi.fn(),
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

const courseData = { id: 1, title: '验收课程', status: 'published' }
const chapterData = (lessons) => ({ id: 11, title: '第一章', order_index: 1, lessons: lessons || [] })
const lessonData = (id, title, status = 'published') => ({
  id,
  chapter_id: 11,
  title,
  content_type: 'markdown',
  order_index: id,
  status,
})

async function mountPage() {
  const mod = await import('../ChapterManageView.vue')
  return mount(mod.default, {
    global: {
      stubs: {
        'router-link': { template: '<a><slot /></a>' },
        AppLayout: { template: '<div><slot /></div>' },
      },
    },
  })
}

/** 在已展开的菜单中按文本找按钮并点击 */
async function clickMenuButton(wrapper, text) {
  const button = wrapper.findAll('.action-menu button').find((b) => b.text().includes(text))
  expect(button, `菜单中应包含「${text}」`).toBeDefined()
  await button.trigger('click')
}

describe('课程管理页 ChapterManageView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('加载并展示课程名、章节名和课时名', async () => {
    coursesAPI.get.mockResolvedValue({ data: courseData })
    coursesAPI.getChapters.mockResolvedValue({
      data: [chapterData([lessonData(111, '第一课')])],
    })

    const wrapper = await mountPage()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('验收课程')
    expect(text).toContain('第一章')
    expect(text).toContain('第一课')
    expect(coursesAPI.get).toHaveBeenCalledWith('1')
    expect(coursesAPI.getChapters).toHaveBeenCalledWith('1')
  })

  it('已发布与草稿课时显示对应状态标签，且不重复', async () => {
    coursesAPI.get.mockResolvedValue({ data: courseData })
    coursesAPI.getChapters.mockResolvedValue({
      data: [chapterData([lessonData(111, '已发布课', 'published'), lessonData(112, '草稿课', 'draft')])],
    })

    const wrapper = await mountPage()
    await flushPromises()

    const statuses = wrapper.findAll('.publish-status').map((el) => el.text())
    expect(statuses).toEqual(['已发布', '草稿'])
    // 状态只出现一次：页面中"已发布"文本个数等于状态标签个数
    expect(wrapper.findAll('.publish-status.published').length).toBe(1)
  })

  it('章节更多菜单包含复制、上移、下移、取消发布与删除，首章上移禁用', async () => {
    coursesAPI.get.mockResolvedValue({ data: courseData })
    coursesAPI.getChapters.mockResolvedValue({
      data: [chapterData([lessonData(111, '第一课', 'published')])],
    })

    const wrapper = await mountPage()
    await flushPromises()
    await wrapper.find('[aria-label="章节更多操作"]').trigger('click')

    expect(wrapper.text()).toContain('复制章节')
    expect(wrapper.text()).toContain('上移')
    expect(wrapper.text()).toContain('下移')
    expect(wrapper.text()).toContain('取消发布章节')
    expect(wrapper.text()).toContain('删除章节')

    const upButton = wrapper.findAll('.action-menu button').find((b) => b.text().includes('上移'))
    expect(upButton.attributes('disabled')).toBeDefined()
  })

  it('取消发布章节将章节内全部课时设为草稿', async () => {
    coursesAPI.get.mockResolvedValue({ data: courseData })
    coursesAPI.getChapters.mockResolvedValue({
      data: [chapterData([lessonData(111, '第一课', 'published')])],
    })

    const wrapper = await mountPage()
    await flushPromises()
    await wrapper.find('[aria-label="章节更多操作"]').trigger('click')
    await clickMenuButton(wrapper, '取消发布章节')

    expect(coursesAPI.updateLesson).toHaveBeenCalledWith(111, { status: 'draft' })
  })

  it('删除章节弹出确认框（含课时数提示），确认后调用删除接口', async () => {
    coursesAPI.get.mockResolvedValue({ data: courseData })
    coursesAPI.getChapters.mockResolvedValue({
      data: [chapterData([lessonData(111, '第一课', 'published')])],
    })
    coursesAPI.deleteChapter.mockResolvedValue({})

    const wrapper = await mountPage()
    await flushPromises()
    await wrapper.find('[aria-label="章节更多操作"]').trigger('click')
    await clickMenuButton(wrapper, '删除章节')

    expect(wrapper.text()).toContain('确认删除章节？')
    expect(wrapper.text()).toContain('1 个课时将一并删除')

    await wrapper.findAll('.confirm-actions button').find((b) => b.text().includes('确认删除')).trigger('click')
    await flushPromises()
    expect(coursesAPI.deleteChapter).toHaveBeenCalledWith(11)
  })

  it('课时更多菜单包含复制、移动到其他章节、发布切换与删除', async () => {
    coursesAPI.get.mockResolvedValue({ data: courseData })
    coursesAPI.getChapters.mockResolvedValue({
      data: [chapterData([lessonData(111, '第一课', 'published'), lessonData(112, '草稿课', 'draft')])],
    })

    const wrapper = await mountPage()
    await flushPromises()
    await wrapper.findAll('[aria-label="更多操作"]')[0].trigger('click')

    expect(wrapper.text()).toContain('复制课时')
    expect(wrapper.text()).toContain('移动到其他章节')
    // 已发布课时显示"设为草稿"
    expect(wrapper.text()).toContain('设为草稿')
    expect(wrapper.text()).toContain('删除课时')
    // 打开草稿课时菜单应显示"发布课时"
    await wrapper.find('[aria-label="更多操作"]').trigger('click') // 关闭当前菜单
    await wrapper.findAll('[aria-label="更多操作"]')[1].trigger('click')
    expect(wrapper.text()).toContain('发布课时')
  })

  it('草稿课时点击发布课时调用状态更新接口', async () => {
    coursesAPI.get.mockResolvedValue({ data: courseData })
    coursesAPI.getChapters.mockResolvedValue({
      data: [chapterData([lessonData(111, '草稿课', 'draft')])],
    })
    coursesAPI.updateLesson.mockResolvedValue({})

    const wrapper = await mountPage()
    await flushPromises()
    await wrapper.find('[aria-label="更多操作"]').trigger('click')
    await clickMenuButton(wrapper, '发布课时')

    expect(coursesAPI.updateLesson).toHaveBeenCalledWith(111, { status: 'published' })
  })

  it('删除课时弹出确认框，确认后调用删除接口', async () => {
    coursesAPI.get.mockResolvedValue({ data: courseData })
    coursesAPI.getChapters.mockResolvedValue({
      data: [chapterData([lessonData(111, '第一课', 'published')])],
    })
    coursesAPI.deleteLesson.mockResolvedValue({})

    const wrapper = await mountPage()
    await flushPromises()
    await wrapper.find('[aria-label="更多操作"]').trigger('click')
    await clickMenuButton(wrapper, '删除课时')

    expect(wrapper.text()).toContain('确认删除课时？')
    expect(wrapper.text()).toContain('课时“第一课”删除后将无法恢复')

    await wrapper.findAll('.confirm-actions button').find((b) => b.text().includes('确认删除')).trigger('click')
    await flushPromises()
    expect(coursesAPI.deleteLesson).toHaveBeenCalledWith(111)
  })

  it('编辑章节打开抽屉并保存标题', async () => {
    coursesAPI.get.mockResolvedValue({ data: courseData })
    coursesAPI.getChapters.mockResolvedValue({
      data: [chapterData([lessonData(111, '第一课', 'published')])],
    })
    coursesAPI.updateChapter.mockResolvedValue({})

    const wrapper = await mountPage()
    await flushPromises()
    const editChapterButton = wrapper.findAll('.text-button').find((b) => b.text().includes('编辑章节'))
    expect(editChapterButton).toBeDefined()
    await editChapterButton.trigger('click')

    const input = wrapper.find('.side-panel input')
    await input.setValue('第一章改名')
    await wrapper.find('form.side-panel').trigger('submit')
    await flushPromises()

    expect(coursesAPI.updateChapter).toHaveBeenCalledWith(11, { title: '第一章改名' })
  })

  it('移动课时到其他章节调用更新接口', async () => {
    coursesAPI.get.mockResolvedValue({ data: courseData })
    coursesAPI.getChapters.mockResolvedValue({
      data: [
        chapterData([lessonData(111, '第一课', 'published')]),
        { id: 12, title: '第二章', order_index: 2, lessons: [] },
      ],
    })
    coursesAPI.updateLesson.mockResolvedValue({})

    const wrapper = await mountPage()
    await flushPromises()
    await wrapper.find('[aria-label="更多操作"]').trigger('click')
    await clickMenuButton(wrapper, '移动到其他章节')

    expect(wrapper.text()).toContain('移动课时')
    await wrapper.find('.confirm-panel select').setValue('12')
    await wrapper.find('form.confirm-panel').trigger('submit')
    await flushPromises()

    expect(coursesAPI.updateLesson).toHaveBeenCalledWith(111, { chapter_id: 12, order_index: 0 })
  })
})
