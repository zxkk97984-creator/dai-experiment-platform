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
import { studioAPI } from '../../../api/studio.js'

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

// ── 添加课时两步弹窗（居中弹窗 → 选类型 → 填表单 → 跳转编辑页） ──
describe('添加课时两步弹窗', () => {
  async function mountWithLesson() {
    coursesAPI.get.mockResolvedValue({ data: courseData })
    coursesAPI.getChapters.mockResolvedValue({
      data: [chapterData([lessonData(111, '第一课', 'published')])],
    })
    const wrapper = await mountPage()
    await flushPromises()
    return wrapper
  }

  async function openWizard(wrapper) {
    const addBtn = wrapper.findAll('button').find((b) => b.text().includes('添加课时'))
    expect(addBtn, '页面应有添加课时按钮').toBeDefined()
    await addBtn.trigger('click')
    await flushPromises()
  }

  async function pickType(wrapper, label) {
    const card = wrapper.findAll('.create-type-card').find((c) => c.text().includes(label))
    expect(card, `类型卡片应包含「${label}」`).toBeDefined()
    await card.trigger('click')
    await flushPromises()
  }

  it('第一步显示四类卡片，选择讲义进入第二步表单', async () => {
    const wrapper = await mountWithLesson()
    await openWizard(wrapper)

    const cards = wrapper.findAll('.create-type-card')
    expect(cards.length).toBe(4)
    expect(wrapper.text()).toContain('讲义')
    expect(wrapper.text()).toContain('Notebook 实验')
    expect(wrapper.text()).toContain('普通实验')
    expect(wrapper.text()).toContain('视频')

    await pickType(wrapper, '讲义')
    const form = wrapper.find('.create-form')
    expect(form.exists()).toBe(true)
    expect(wrapper.text()).toContain('课时名称')
    expect(wrapper.text()).toContain('创建并编辑')
  })

  it('讲义：填标题+简介提交 → createLesson payload 正确并跳转编辑页', async () => {
    coursesAPI.createLesson.mockResolvedValue({ data: { id: 555 } })
    const wrapper = await mountWithLesson()
    await openWizard(wrapper)
    await pickType(wrapper, '讲义')
    await wrapper.find('.create-form input').setValue('新讲义')
    await wrapper.find('.create-form textarea').setValue('简介内容')
    await wrapper.find('.create-form').trigger('submit')
    await flushPromises()

    expect(coursesAPI.createLesson).toHaveBeenCalledWith(11, {
      title: '新讲义',
      content_type: 'markdown',
      content: '简介内容',
      order_index: 0,
    })
    expect(push).toHaveBeenCalledWith('/teacher/courses/1/lessons/555/edit')
  })

  it('普通实验：content 按 # 实验任务 / # 提交要求 拼接', async () => {
    coursesAPI.createLesson.mockResolvedValue({ data: { id: 556 } })
    const wrapper = await mountWithLesson()
    await openWizard(wrapper)
    await pickType(wrapper, '普通实验')
    await wrapper.find('.create-form input').setValue('实验课')
    await wrapper.find('.create-form textarea').setValue('任务描述')
    await wrapper.find('.create-form').trigger('submit')
    await flushPromises()

    expect(coursesAPI.createLesson).toHaveBeenCalledWith(11, {
      title: '实验课',
      content_type: 'experiment',
      content: '# 实验任务\n\n任务描述\n\n# 提交要求\n\n',
      order_index: 0,
    })
    expect(push).toHaveBeenCalledWith('/teacher/courses/1/lessons/556/edit')
  })

  it('视频：显示链接输入框，payload 含 video_url', async () => {
    coursesAPI.createLesson.mockResolvedValue({ data: { id: 557 } })
    const wrapper = await mountWithLesson()
    await openWizard(wrapper)
    await pickType(wrapper, '视频')
    // 视频类型第二步有标题 + 链接两个输入框
    const inputs = wrapper.findAll('.create-form input')
    expect(inputs.length).toBe(2)
    await inputs[0].setValue('视频课')
    await inputs[1].setValue('https://v.example.com/x.mp4')
    await wrapper.find('.create-form textarea').setValue('视频简介')
    await wrapper.find('.create-form').trigger('submit')
    await flushPromises()

    expect(coursesAPI.createLesson).toHaveBeenCalledWith(11, {
      title: '视频课',
      content_type: 'video',
      content: '视频简介',
      video_url: 'https://v.example.com/x.mp4',
      order_index: 0,
    })
    expect(push).toHaveBeenCalledWith('/teacher/courses/1/lessons/557/edit')
  })

  it('Notebook：创建课时后创建模板，push 编辑页带 ?template', async () => {
    coursesAPI.createLesson.mockResolvedValue({ data: { id: 558 } })
    studioAPI.createTemplate.mockResolvedValue({ data: { id: 666 } })
    const wrapper = await mountWithLesson()
    await openWizard(wrapper)
    await pickType(wrapper, 'Notebook')
    await wrapper.find('.create-form input').setValue('实验簿')
    await wrapper.find('.create-form textarea').setValue('簿简介')
    await wrapper.find('.create-form').trigger('submit')
    await flushPromises()

    expect(coursesAPI.createLesson).toHaveBeenCalledWith(11, {
      title: '实验簿',
      content_type: 'notebook',
      order_index: 0,
    })
    expect(studioAPI.createTemplate).toHaveBeenCalledWith({
      name: '实验簿',
      description: '簿简介',
      lesson_id: 558,
    })
    expect(push).toHaveBeenCalledWith('/teacher/courses/1/lessons/558/edit?template=666')
  })

  it('标题为空时提交禁用；上一步可返回类型选择', async () => {
    const wrapper = await mountWithLesson()
    await openWizard(wrapper)
    await pickType(wrapper, '讲义')
    const submit = wrapper.find('.create-form button[type="submit"]')
    expect(submit.attributes('disabled')).toBeDefined()

    await wrapper.findAll('.create-form button').find((b) => b.text() === '上一步').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.create-type-card').length).toBe(4)
  })

  it('关闭按钮 / 遮罩点击 / Escape 均可关闭弹窗', async () => {
    const wrapper = await mountWithLesson()
    // 关闭按钮
    await openWizard(wrapper)
    await wrapper.find('.create-close').trigger('click')
    expect(wrapper.find('.create-panel').exists()).toBe(false)
    // 遮罩 @click.self
    await openWizard(wrapper)
    await wrapper.find('.create-backdrop').trigger('click')
    expect(wrapper.find('.create-panel').exists()).toBe(false)
    // Escape
    await openWizard(wrapper)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(wrapper.find('.create-panel').exists()).toBe(false)
  })

  it('点课时行"编辑"统一跳转编辑页（原 notebook 特判被取代）', async () => {
    const wrapper = await mountWithLesson()
    const editBtn = wrapper.findAll('.row-action').find((b) => b.text().includes('编辑'))
    expect(editBtn).toBeDefined()
    await editBtn.trigger('click')
    await flushPromises()
    expect(push).toHaveBeenCalledWith('/teacher/courses/1/lessons/111/edit')
  })
})
