// 课时编辑分派壳：按 content_type 分派、notebook 模板解析三态、错误态
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import LessonEditView from '../LessonEditView.vue'

const routeState = vi.hoisted(() => ({
  params: { courseId: '1', lessonId: '2' },
  query: {},
}))
const routerState = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
}))
const appState = vi.hoisted(() => ({ showToast: vi.fn() }))

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
  environmentsAPI: { listAvailable: vi.fn().mockResolvedValue({ data: [] }) },
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

  it('notebook 无 query 时走 listTemplates 反查模板 id', async () => {
    coursesAPI.getChapters.mockResolvedValue(
      { data: chapterWith({ id: 2, title: '实验簿', content_type: 'notebook' }) },
    )
    studioAPI.listTemplates.mockResolvedValue({
      data: [{ id: 7, lesson_id: 2, name: '匹配模板' }, { id: 8, lesson_id: 99 }],
    })
    const wrapper = await mountPage()
    expect(studioAPI.listTemplates).toHaveBeenCalledWith({})
    const studio = wrapper.findComponent({ name: 'StudioEditor' })
    expect(studio.exists()).toBe(true)
    expect(studio.props('templateId')).toBe(7)
  })

  it('notebook 未关联模板 → 兜底卡片 → 创建模板并进入（replace 带新 template）', async () => {
    coursesAPI.getChapters.mockResolvedValue(
      { data: chapterWith({ id: 2, title: '复制实验簿', content_type: 'notebook', content: '简介' }) },
    )
    studioAPI.listTemplates.mockResolvedValue({ data: [] })
    studioAPI.createTemplate.mockResolvedValue({ data: { id: 99 } })
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('该 Notebook 课时尚未关联模板')
    expect(wrapper.text()).toContain('暂无可用环境，请联系管理员')
    await wrapper.findAll('button').find((b) => b.text().includes('创建模板并进入')).trigger('click')
    await flushPromises()
    // Phase 4：兜底创建携带环境字段（无可用环境时为 null + 默认策略）
    expect(studioAPI.createTemplate).toHaveBeenCalledWith({
      name: '复制实验簿',
      description: '简介',
      lesson_id: 2,
      environment_version_id: null,
      import_policy_mode: 'unrestricted',
      allowed_imports: [],
    })
    expect(routerState.replace).toHaveBeenCalledWith({ query: { template: 99 } })
  })

  it('课时不存在 → 错误卡片与返回按钮', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterWith({ id: 999, title: '别的课时', content_type: 'markdown' }) })
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('课时不存在或已被删除')
    await wrapper.findAll('button').find((b) => b.text() === '返回').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/teacher/courses/1/manage')
  })
})
