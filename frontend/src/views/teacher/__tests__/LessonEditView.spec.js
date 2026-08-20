// 课时编辑分派壳：按 content_type 分派、notebook 模板解析三态、错误态
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import LessonEditView from '../LessonEditView.vue'

const lessonEditViewSource = readFileSync(resolve(process.cwd(), 'src/views/teacher/LessonEditView.vue'), 'utf8')
const lessonEditViewStyles = lessonEditViewSource.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] || ''

const routeState = vi.hoisted(() => ({
  params: { courseId: '1', lessonId: '2' },
  query: {},
}))
const routerState = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
}))
const appState = vi.hoisted(() => ({ showToast: vi.fn() }))
const environmentsState = vi.hoisted(() => ({
  listAvailable: vi.fn().mockResolvedValue({ data: [] }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => routerState,
  // client.js 链式加载真实 router/index.js，与 ChapterManageView.spec 同款 mock
  createRouter: vi.fn(() => ({
    beforeEach: vi.fn(),
    afterEach: vi.fn(),
    beforeResolve: vi.fn(),
    push: vi.fn(),
    replace: vi.fn(),
    currentRoute: { value: { path: '/' } },
  })),
  createWebHistory: vi.fn(() => ({})),
}))

vi.mock('../../../api/courses.js', () => ({
  coursesAPI: { getChapters: vi.fn() },
}))

vi.mock('../../../api/studio.js', () => ({
  studioAPI: {
    listTemplates: vi.fn(),
    createTemplate: vi.fn(),
  },
}))

vi.mock('../../../api/environments.js', () => ({
  environmentsAPI: environmentsState,
}))

vi.mock('../../../stores/app.js', () => ({
  useAppStore: () => appState,
}))

import { coursesAPI } from '../../../api/courses.js'
import { studioAPI } from '../../../api/studio.js'

const EditorStubs = {
  LessonMarkdownEditor: {
    name: 'LessonMarkdownEditor',
    props: ['courseId', 'lessonId', 'backPath'],
    template: '<div class="md-editor-stub" />',
  },
  LessonExperimentEditor: {
    name: 'LessonExperimentEditor',
    props: ['courseId', 'lessonId', 'backPath'],
    template: '<div class="exp-editor-stub" />',
  },
  LessonVideoEditor: {
    name: 'LessonVideoEditor',
    props: ['courseId', 'lessonId', 'backPath'],
    template: '<div class="video-editor-stub" />',
  },
  StudioEditor: {
    name: 'StudioEditor',
    props: ['templateId', 'backTo'],
    template: '<div class="studio-stub" />',
  },
  AppLayout: { name: 'AppLayout', template: '<div><slot /></div>' },
}

function chapterWith(lesson) {
  return [{ id: 11, lessons: [lesson] }]
}

async function mountPage() {
  const wrapper = mount(LessonEditView, { global: { stubs: EditorStubs } })
  await flushPromises()
  return wrapper
}

describe('LessonEditView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    routeState.params = { courseId: '1', lessonId: '2' }
    routeState.query = {}
    environmentsState.listAvailable.mockResolvedValue({ data: [] })
  })

  it('markdown 课时分派到讲义编辑页并传 props', async () => {
    coursesAPI.getChapters.mockResolvedValue(
      { data: chapterWith({ id: 2, title: '讲义', content_type: 'markdown' }) },
    )
    const wrapper = await mountPage()
    const editor = wrapper.findComponent({ name: 'LessonMarkdownEditor' })
    expect(editor.exists()).toBe(true)
    expect(editor.props('courseId')).toBe('1')
    expect(editor.props('lessonId')).toBe('2')
    expect(editor.props('backPath')).toBe('/teacher/courses/1/manage')
  })

  it('experiment / video 分别分派对应编辑器', async () => {
    coursesAPI.getChapters.mockResolvedValue(
      { data: chapterWith({ id: 2, title: '实验', content_type: 'experiment' }) },
    )
    let wrapper = await mountPage()
    expect(wrapper.findComponent({ name: 'LessonExperimentEditor' }).exists()).toBe(true)

    coursesAPI.getChapters.mockResolvedValue(
      { data: chapterWith({ id: 2, title: '视频', content_type: 'video' }) },
    )
    wrapper = await mountPage()
    expect(wrapper.findComponent({ name: 'LessonVideoEditor' }).exists()).toBe(true)
  })

  it('notebook 带 ?template 直接渲染 StudioEditor', async () => {
    routeState.query = { template: '5' }
    coursesAPI.getChapters.mockResolvedValue(
      { data: chapterWith({ id: 2, title: '实验簿', content_type: 'notebook' }) },
    )
    const wrapper = await mountPage()
    const studio = wrapper.findComponent({ name: 'StudioEditor' })
    expect(studio.exists()).toBe(true)
    expect(studio.props('templateId')).toBe(5)
    expect(studio.props('backTo')).toBe('/teacher/courses/1/manage')
    expect(studioAPI.listTemplates).not.toHaveBeenCalled()
  })

  it('notebook 已有关联模板时直接渲染 StudioEditor，不反查模板列表', async () => {
    coursesAPI.getChapters.mockResolvedValue(
      { data: chapterWith({ id: 2, title: '实验簿', content_type: 'notebook', template_id: 7 }) },
    )
    const wrapper = await mountPage()
    expect(studioAPI.listTemplates).not.toHaveBeenCalled()
    const studio = wrapper.findComponent({ name: 'StudioEditor' })
    expect(studio.exists()).toBe(true)
    expect(studio.props('templateId')).toBe(7)
  })

  it('notebook 未关联模板时显示首次配置，并在选择环境后进入 Studio', async () => {
    coursesAPI.getChapters.mockResolvedValue(
      { data: chapterWith({ id: 2, title: '复制实验簿', content_type: 'notebook', content: '简介' }) },
    )
    environmentsState.listAvailable.mockResolvedValue({
      data: [{
        environment_version_id: 12,
        display_name: 'Python 基础',
        version_number: 1,
        packages: [],
      }],
    })
    studioAPI.createTemplate.mockResolvedValue({ data: { id: 99 } })
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('首次进入 Notebook')
    expect(wrapper.text()).toContain('请选择运行环境')
    expect(wrapper.text()).not.toContain('尚未关联模板')
    expect(wrapper.find('.course-form-panel').exists()).toBe(true)
    expect(wrapper.find('.setup-card').exists()).toBe(false)
    const importRuleLabel = wrapper.find('label[for="fallback-import-policy"]')
    expect(importRuleLabel.exists()).toBe(true)
    expect(importRuleLabel.text()).toBe('导入规则')
    expect(lessonEditViewStyles).toMatch(/\.fallback-select\s*\{[\s\S]*height:\s*auto;/)
    const enterButton = wrapper.findAll('button').find((b) => b.text() === '进入 Studio')
    expect(enterButton.attributes('disabled')).toBeUndefined()
    await wrapper.find('.course-form-panel').trigger('submit')
    await flushPromises()
    // 自动创建内部模板并携带教师选择的环境
    expect(studioAPI.createTemplate).toHaveBeenCalledWith({
      name: '复制实验簿',
      description: '简介',
      lesson_id: 2,
      environment_version_id: 12,
      import_policy_mode: 'unrestricted',
      allowed_imports: [],
    })
    expect(routerState.replace).toHaveBeenCalledWith({ query: { template: 99 } })
  })

  it('notebook 未关联模板且没有可用环境时禁止进入 Studio', async () => {
    coursesAPI.getChapters.mockResolvedValue(
      { data: chapterWith({ id: 2, title: '复制实验簿', content_type: 'notebook' }) },
    )
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('暂无可用环境，请联系管理员')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    const enterButton = wrapper.findAll('button').find((b) => b.text() === '进入 Studio')
    expect(enterButton.attributes('disabled')).toBeDefined()
    await wrapper.findAll('button').find((b) => b.text() === '取消').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/teacher/courses/1/manage')
  })

  it('课时不存在 → 错误卡片与返回按钮', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterWith({ id: 999, title: '别的课时', content_type: 'markdown' }) })
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('课时不存在或已被删除')
    await wrapper.findAll('button').find((b) => b.text() === '返回').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/teacher/courses/1/manage')
  })
})
