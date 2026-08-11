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
    update: vi.fn(),
    deleteChapter: vi.fn(),
    deleteLesson: vi.fn(),
    listWhitelist: vi.fn(),
    addWhitelistStudent: vi.fn(),
    removeWhitelistStudent: vi.fn(),
    getLessonVideoPlaybackUrl: vi.fn(),
    uploadCourseCover: vi.fn(),
    deleteCourseCover: vi.fn(),
  },
}))

vi.mock('../../../api/users', () => ({
  usersAPI: {
    listStudents: vi.fn(),
  },
}))

vi.mock('../../../api/studio', () => ({
  studioAPI: {
    createTemplate: vi.fn(),
  },
}))

vi.mock('../../../api/environments', () => ({
  environmentsAPI: { listAvailable: vi.fn() },
}))

vi.mock('../../../stores/app', () => ({
  useAppStore: () => ({
    showToast: vi.fn(),
  }),
}))

import CourseCoverUploader from '../../../components/teacher/CourseCoverUploader.vue'
import { coursesAPI } from '../../../api/courses.js'
import { studioAPI } from '../../../api/studio.js'
import { usersAPI } from '../../../api/users.js'
import { environmentsAPI } from '../../../api/environments.js'

// Phase 4：Notebook 创建向导的环境选项
const envOptions = [
  {
    profile_id: 1, environment_version_id: 21, slug: 'basic', display_name: 'Python 基础',
    version_number: 1, packages: [{ pip_name: 'pytest', locked_version: '8.3.4', import_names: ['pytest'] }],
    minimum_memory_mb: 256,
  },
]

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

  it('课程管理页提供保存和发布操作，发布成功后更新课程状态', async () => {
    const draftCourse = {
      ...courseData,
      status: 'draft',
      description: '课程简介',
      cover: 'covers/course.png',
      start_time: '2026-09-01T08:00:00',
      visibility: 'class',
      default_score: 100,
      academic_term_id: 1,
      teaching_classes: [{ id: 10, name: 'Python 程序设计 1 班' }],
    }
    coursesAPI.get.mockResolvedValue({ data: draftCourse })
    coursesAPI.getChapters.mockResolvedValue({ data: [] })
    coursesAPI.update.mockResolvedValue({ data: { ...draftCourse, status: 'published' } })

    const wrapper = await mountPage()
    await flushPromises()

    expect(wrapper.findAll('.overview-actions button').map((button) => button.text())).toEqual([
      '保存草稿', '课程设置', '新增章节', '发布课程',
    ])
    await wrapper.findAll('.overview-actions button').find((button) => button.text() === '发布课程').trigger('click')
    await flushPromises()

    expect(coursesAPI.update).toHaveBeenCalledWith('1', { status: 'published' })
    expect(wrapper.text()).toContain('已发布')
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
    // 已发布 → 设为草稿：闭眼图标（隐藏）
    expect(wrapper.find('[data-icon="eye-off"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('删除课时')
    // 打开草稿课时菜单应显示"发布课时"
    await wrapper.find('[aria-label="更多操作"]').trigger('click') // 关闭当前菜单
    await wrapper.findAll('[aria-label="更多操作"]')[1].trigger('click')
    expect(wrapper.text()).toContain('发布课时')
    // 草稿 → 发布课时：睁眼图标（可见）
    expect(wrapper.find('[data-icon="eye"]').exists()).toBe(true)
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

  it('课程设置保存时提交开课时间、可见范围与默认评分，payload 不含 cover', async () => {
    coursesAPI.get.mockResolvedValue({
      data: {
        ...courseData,
        cover: 'covers/1/old.png',
        start_time: '2026-09-01T09:00:00+08:00',
        visibility: 'private',
        default_score: 100,
      },
    })
    coursesAPI.getChapters.mockResolvedValue({ data: [chapterData()] })
    coursesAPI.update.mockResolvedValue({})

    const wrapper = await mountPage()
    await flushPromises()
    const openSettingsButton = wrapper.findAll('button').find((b) => b.text().includes('课程设置'))
    expect(openSettingsButton).toBeDefined()
    await openSettingsButton.trigger('click')

    // 后端字段应回填（datetime-local 截取前 16 位）
    expect(wrapper.find('input[type="datetime-local"]').element.value).toBe('2026-09-01T09:00')

    // 修改开课时间、默认评分后保存
    await wrapper.find('input[type="datetime-local"]').setValue('2026-10-01T10:30')
    await wrapper.find('input[type="number"]').setValue('95')
    await wrapper.find('form.side-panel').trigger('submit')
    await flushPromises()

    expect(coursesAPI.update).toHaveBeenCalledWith(
      '1',
      expect.objectContaining({
        start_time: '2026-10-01T10:30',
        visibility: 'private',
        default_score: 95,
      }),
    )
    // 封面由上传组件独立提交，普通设置 payload 必须排除 cover
    expect(coursesAPI.update.mock.calls[0][1]).not.toHaveProperty('cover')
  })

  it('课程设置保存时开课时间留空会以 null 清空', async () => {
    coursesAPI.get.mockResolvedValue({
      data: { ...courseData, start_time: '2026-09-01T09:00:00+08:00', default_score: 100 },
    })
    coursesAPI.getChapters.mockResolvedValue({ data: [chapterData()] })
    coursesAPI.update.mockResolvedValue({})

    const wrapper = await mountPage()
    await flushPromises()
    const openSettingsButton = wrapper.findAll('button').find((b) => b.text().includes('课程设置'))
    await openSettingsButton.trigger('click')

    await wrapper.find('input[type="datetime-local"]').setValue('')
    await wrapper.find('form.side-panel').trigger('submit')
    await flushPromises()

    expect(coursesAPI.update).toHaveBeenCalledWith('1', expect.objectContaining({ start_time: null }))
  })

  it('课程设置抽屉不含封面 URL/path 输入框', async () => {
    coursesAPI.get.mockResolvedValue({
      data: { ...courseData, cover: 'covers/1/abc.png' },
    })
    coursesAPI.getChapters.mockResolvedValue({ data: [chapterData()] })
    coursesAPI.update.mockResolvedValue({})

    const wrapper = await mountPage()
    await flushPromises()
    const openSettingsButton = wrapper.findAll('button').find((b) => b.text().includes('课程设置'))
    await openSettingsButton.trigger('click')

    expect(wrapper.findAll('input[placeholder*="封面"]').length).toBe(0)
    expect(wrapper.text()).not.toContain('封面图片 URL')
  })

  it('封面上传组件接收当前课程与 courseId', async () => {
    coursesAPI.get.mockResolvedValue({
      data: { ...courseData, cover: 'covers/1/abc.png' },
    })
    coursesAPI.getChapters.mockResolvedValue({ data: [chapterData()] })
    coursesAPI.update.mockResolvedValue({})

    const wrapper = await mountPage()
    await flushPromises()
    const openSettingsButton = wrapper.findAll('button').find((b) => b.text().includes('课程设置'))
    await openSettingsButton.trigger('click')

    const uploader = wrapper.findComponent(CourseCoverUploader)
    expect(uploader.exists()).toBe(true)
    expect(uploader.props('courseId')).toBe('1')
    expect(uploader.props('course').cover).toBe('covers/1/abc.png')
  })

  it('上传/移除事件更新当前课程封面，期间禁用保存按钮', async () => {
    coursesAPI.get.mockResolvedValue({ data: { ...courseData } })
    coursesAPI.getChapters.mockResolvedValue({ data: [chapterData()] })
    coursesAPI.update.mockResolvedValue({})

    const wrapper = await mountPage()
    await flushPromises()
    const openSettingsButton = wrapper.findAll('button').find((b) => b.text().includes('课程设置'))
    await openSettingsButton.trigger('click')

    const uploader = wrapper.findComponent(CourseCoverUploader)
    const saveButton = wrapper.find('form.side-panel button[type="submit"]')

    // busy-change: true → 保存按钮禁用
    uploader.vm.$emit('busy-change', true)
    await flushPromises()
    expect(saveButton.attributes('disabled')).toBeDefined()

    // 上传成功：updated 携带 API 返回课程 → 当前课程封面更新
    uploader.vm.$emit('updated', { ...courseData, cover: 'covers/1/new.png' })
    await flushPromises()
    expect(uploader.props('course').cover).toBe('covers/1/new.png')

    // 移除：updated 携带 cover: null → 封面清空
    uploader.vm.$emit('updated', { ...courseData, cover: null })
    await flushPromises()
    expect(uploader.props('course').cover).toBeNull()

    // busy-change: false → 保存按钮恢复可用
    uploader.vm.$emit('busy-change', false)
    await flushPromises()
    expect(saveButton.attributes('disabled')).toBeUndefined()
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

  it('视频：只填名称与简介，提示创建后进编辑页上传，payload 不含 video_url', async () => {
    coursesAPI.createLesson.mockResolvedValue({ data: { id: 557 } })
    const wrapper = await mountWithLesson()
    await openWizard(wrapper)
    await pickType(wrapper, '视频')
    // 视频类型第二步只有标题一个输入框（URL 输入已移除）
    const inputs = wrapper.findAll('.create-form input')
    expect(inputs.length).toBe(1)
    // 创建弹窗不直接上传：提示创建后进入编辑页上传
    expect(wrapper.text()).toContain('视频可在创建后进入编辑页上传')
    await inputs[0].setValue('视频课')
    await wrapper.find('.create-form textarea').setValue('视频简介')
    await wrapper.find('.create-form').trigger('submit')
    await flushPromises()

    expect(coursesAPI.createLesson).toHaveBeenCalledWith(11, {
      title: '视频课',
      content_type: 'video',
      content: '视频简介',
      order_index: 0,
    })
    expect(push).toHaveBeenCalledWith('/teacher/courses/1/lessons/557/edit')
  })

  it('Notebook：创建课时后创建模板（携带环境），push 编辑页带 ?template', async () => {
    coursesAPI.createLesson.mockResolvedValue({ data: { id: 558 } })
    studioAPI.createTemplate.mockResolvedValue({ data: { id: 666 } })
    environmentsAPI.listAvailable.mockResolvedValue({ data: envOptions })
    const wrapper = await mountWithLesson()
    await openWizard(wrapper)
    await pickType(wrapper, 'Notebook')
    await wrapper.find('.create-form input').setValue('实验簿')
    await wrapper.find('.create-form textarea').setValue('簿简介')
    // 环境列表加载完成后默认选中 basic（第一项）
    await flushPromises()
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
      environment_version_id: 21,
      import_policy_mode: 'unrestricted',
      allowed_imports: [],
    })
    expect(push).toHaveBeenCalledWith('/teacher/courses/1/lessons/558/edit?template=666')
  })

  it('Notebook：无可用环境时提示联系管理员，创建仍以 null 环境提交', async () => {
    coursesAPI.createLesson.mockResolvedValue({ data: { id: 559 } })
    studioAPI.createTemplate.mockResolvedValue({ data: { id: 667 } })
    environmentsAPI.listAvailable.mockResolvedValue({ data: [] })
    const wrapper = await mountWithLesson()
    await openWizard(wrapper)
    await pickType(wrapper, 'Notebook')
    expect(wrapper.text()).toContain('暂无可用环境，请联系管理员')
    await wrapper.find('.create-form input').setValue('无环境簿')
    await wrapper.find('.create-form').trigger('submit')
    await flushPromises()

    expect(studioAPI.createTemplate).toHaveBeenCalledWith(
      expect.objectContaining({ environment_version_id: null, import_policy_mode: 'unrestricted' }),
    )
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

// ── 课程可见范围设置（private / class / whitelist） ──
describe('课程可见范围设置', () => {
  async function mountWithSettings(visibility = 'private') {
    coursesAPI.get.mockResolvedValue({
      data: { ...courseData, visibility, default_score: 100 },
    })
    coursesAPI.getChapters.mockResolvedValue({ data: [chapterData()] })
    coursesAPI.update.mockResolvedValue({})
    coursesAPI.listWhitelist.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 20 } })
    usersAPI.listStudents.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 20 } })
    const wrapper = await mountPage()
    await flushPromises()
    const openSettingsButton = wrapper.findAll('button').find((b) => b.text().includes('课程设置'))
    await openSettingsButton.trigger('click')
    await flushPromises()
    return wrapper
  }

  const visSelect = (wrapper) => wrapper.get('[data-testid="visibility-select"]')

  it('可见范围 select 提供 private / class / whitelist 三个选项', async () => {
    const wrapper = await mountWithSettings()
    const options = visSelect(wrapper).findAll('option').map((o) => o.attributes('value'))
    expect(options).toEqual(['private', 'class', 'whitelist'])
  })

  it('选择 whitelist 显示白名单管理组件，并接收正确 courseId', async () => {
    const wrapper = await mountWithSettings()
    expect(wrapper.find('.whitelist-manager').exists()).toBe(false)
    await visSelect(wrapper).setValue('whitelist')
    await flushPromises()
    const manager = wrapper.find('.whitelist-manager')
    expect(manager.exists()).toBe(true)
    expect(coursesAPI.listWhitelist).toHaveBeenCalledWith('1', expect.objectContaining({ page_size: 20 }))
    expect(usersAPI.listStudents).toHaveBeenCalled()
  })

  it('选择 private / class 时隐藏白名单管理组件', async () => {
    const wrapper = await mountWithSettings()
    await visSelect(wrapper).setValue('whitelist')
    await flushPromises()
    expect(wrapper.find('.whitelist-manager').exists()).toBe(true)
    await visSelect(wrapper).setValue('private')
    await flushPromises()
    expect(wrapper.find('.whitelist-manager').exists()).toBe(false)
    await visSelect(wrapper).setValue('class')
    await flushPromises()
    expect(wrapper.find('.whitelist-manager').exists()).toBe(false)
  })

  it('保存时提交所选 visibility', async () => {
    const wrapper = await mountWithSettings()
    await visSelect(wrapper).setValue('whitelist')
    await wrapper.find('form.side-panel').trigger('submit')
    await flushPromises()
    expect(coursesAPI.update).toHaveBeenCalledWith(
      '1',
      expect.objectContaining({ visibility: 'whitelist' }),
    )
  })

  it('后端返回 whitelist 时正确回填并显示组件', async () => {
    const wrapper = await mountWithSettings('whitelist')
    expect(visSelect(wrapper).element.value).toBe('whitelist')
    expect(wrapper.find('.whitelist-manager').exists()).toBe(true)
  })

  it('关闭再打开设置抽屉时保留可见范围选择（不丢失未保存修改）', async () => {
    const wrapper = await mountWithSettings()
    await visSelect(wrapper).setValue('class')
    await wrapper.find('.panel-header .icon-button').trigger('click')
    await flushPromises()
    expect(wrapper.find('.side-panel').exists()).toBe(false)
    // 重新打开：可见范围选择保留
    const openSettingsButton = wrapper.findAll('button').find((b) => b.text().includes('课程设置'))
    await openSettingsButton.trigger('click')
    await flushPromises()
    expect(visSelect(wrapper).element.value).toBe('class')
    expect(wrapper.find('.whitelist-manager').exists()).toBe(false)
  })
})

describe('学生视角预览：本地视频', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const videoLesson = (overrides = {}) => ({
    id: 222,
    chapter_id: 11,
    title: '本地视频课',
    content_type: 'video',
    order_index: 222,
    video_source: 'upload',
    video_url: null,
    video_filename: 'demo.mp4',
    video_size: 100,
    ...overrides,
  })

  async function mountWithVideoLesson(lesson) {
    coursesAPI.get.mockResolvedValue({ data: courseData })
    coursesAPI.getChapters.mockResolvedValue({
      data: [chapterData([lesson])],
    })
    const wrapper = await mountPage()
    await flushPromises()
    return wrapper
  }

  async function openVideoPreview(wrapper) {
    const previewBtn = wrapper.findAll('.row-action').find((b) => b.text().includes('预览'))
    expect(previewBtn).toBeDefined()
    await previewBtn.trigger('click')
    await flushPromises()
  }

  it('本地来源预览请求播放 URL 并渲染内嵌播放器', async () => {
    coursesAPI.getLessonVideoPlaybackUrl.mockResolvedValue({
      data: { url: 'http://testserver/media?sig=x' },
    })
    const wrapper = await mountWithVideoLesson(videoLesson())
    await openVideoPreview(wrapper)

    expect(coursesAPI.getLessonVideoPlaybackUrl).toHaveBeenCalledWith(222)
    const video = wrapper.find('.preview-video')
    expect(video.exists()).toBe(true)
    expect(video.attributes('src')).toBe('http://testserver/media?sig=x')
    expect(video.attributes('controls')).toBeDefined()
  })

  it('播放 URL 获取失败显示明确错误态与重试按钮', async () => {
    coursesAPI.getLessonVideoPlaybackUrl.mockRejectedValue({ response: { status: 403 } })
    const wrapper = await mountWithVideoLesson(videoLesson())
    await openVideoPreview(wrapper)

    expect(wrapper.find('.preview-video-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('视频预览加载失败')
    // 不再显示"尚未设置视频地址"
    expect(wrapper.text()).not.toContain('尚未设置视频地址')

    // 重试成功
    coursesAPI.getLessonVideoPlaybackUrl.mockResolvedValue({
      data: { url: 'http://testserver/media?sig=retry' },
    })
    await wrapper.find('.preview-video-error .retry-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.preview-video').attributes('src')).toBe('http://testserver/media?sig=retry')
  })

  it('外链来源预览不调用播放接口，继续显示外链链接', async () => {
    const wrapper = await mountWithVideoLesson({
      id: 223,
      title: '外链视频课',
      content_type: 'video',
      video_source: 'external',
      video_url: 'https://v.example.com/x.mp4',
      video_filename: null,
    })
    await openVideoPreview(wrapper)

    expect(coursesAPI.getLessonVideoPlaybackUrl).not.toHaveBeenCalled()
    const link = wrapper.find('.preview-body a')
    expect(link.attributes('href')).toBe('https://v.example.com/x.mp4')
  })

  it('复制本地视频课时不复制文件字段（副本为空视频课时）', async () => {
    coursesAPI.createLesson.mockResolvedValue({ data: { id: 999 } })
    const wrapper = await mountWithVideoLesson(videoLesson())
    await wrapper.find('[aria-label="更多操作"]').trigger('click')
    await clickMenuButton(wrapper, '复制课时')
    await flushPromises()

    expect(coursesAPI.createLesson).toHaveBeenCalledWith(11, {
      title: '本地视频课（副本）',
      content_type: 'video',
      content: undefined,
      notebook_path: undefined,
      video_url: undefined,
      order_index: 223,
    })
  })
})
