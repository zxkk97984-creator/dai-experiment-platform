// 讲义编辑页：回填、保存、dirty 离开守卫、标题必填、预览渲染
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import LessonMarkdownEditor from '../LessonMarkdownEditor.vue'

const routerState = vi.hoisted(() => ({
  push: vi.fn(),
  leaveHook: null,
}))
const appState = vi.hoisted(() => ({ showToast: vi.fn() }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerState.push }),
  onBeforeRouteLeave: (hook) => {
    routerState.leaveHook = hook
  },
}))

vi.mock('../../../api/courses.js', () => ({
  coursesAPI: {
    getChapters: vi.fn(),
    updateLesson: vi.fn(),
  },
}))

vi.mock('../../../stores/app.js', () => ({
  useAppStore: () => appState,
}))

import { coursesAPI } from '../../../api/courses.js'

const chapterResponse = [
  { id: 11, lessons: [{ id: 2, title: '讲义一课', content_type: 'markdown', content: '# 标题\n正文内容' }] },
]

async function mountEditor() {
  const wrapper = mount(LessonMarkdownEditor, {
    props: { courseId: '1', lessonId: '2', backPath: '/teacher/courses/1/manage' },
  })
  await flushPromises()
  return wrapper
}

describe('LessonMarkdownEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    routerState.leaveHook = null
  })

  it('回填课时标题与正文', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    const wrapper = await mountEditor()
    expect(wrapper.find('.title-input').element.value).toBe('讲义一课')
    expect(wrapper.find('.content-textarea').element.value).toBe('# 标题\n正文内容')
    expect(wrapper.find('.type-badge').text()).toBe('讲义')
  })

  it('修改后保存：updateLesson payload 正确并 toast', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    await wrapper.find('.title-input').setValue('新标题')
    await wrapper.find('.content-textarea').setValue('新正文')
    await wrapper.find('.save-btn').trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', { title: '新标题', content: '新正文' })
    expect(appState.showToast).toHaveBeenCalledWith('课时已保存', 'success')
  })

  it('标题为空时保存按钮禁用', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    const wrapper = await mountEditor()
    await wrapper.find('.title-input').setValue('')
    expect(wrapper.find('.save-btn').attributes('disabled')).toBeDefined()
  })

  it('未修改直接放行离开', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    await mountEditor()
    expect(routerState.leaveHook({}, {})).toBe(true)
  })

  it('有修改时守卫拦截并弹自定义确认框，取消留在页面', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    const wrapper = await mountEditor()
    await wrapper.find('.content-textarea').setValue('改动一下')
    const ret = routerState.leaveHook({}, {})
    expect(ret).toBeInstanceOf(Promise)
    await flushPromises()
    expect(wrapper.text()).toContain('有未保存的修改')
    // 取消 → resolve(false)
    await wrapper.findAll('button').find((b) => b.text() === '取消').trigger('click')
    await flushPromises()
    expect(await ret).toBe(false)
    expect(wrapper.text()).not.toContain('有未保存的修改')
  })

  it('有修改时确认离开 resolve(true)，随后 push 放行', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    const wrapper = await mountEditor()
    await wrapper.find('.content-textarea').setValue('改动一下')
    const ret = routerState.leaveHook({}, {})
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text() === '离开').trigger('click')
    await flushPromises()
    expect(await ret).toBe(true)
  })

  it('预览模式渲染 sanitize 后的 markdown', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    const wrapper = await mountEditor()
    const tabButtons = () => wrapper.findAll('.mode-tabs button')
    await tabButtons().filter((b) => b.text() === '预览')[0].trigger('click')
    const html = wrapper.find('.lesson-content').html()
    expect(html).toContain('<h1')
    expect(html).toContain('正文内容')
    // 危险脚本被 sanitize 剥离
    await tabButtons().filter((b) => b.text() === '编辑')[0].trigger('click')
    await wrapper.find('.content-textarea').setValue('<script>alert(1)</script>正文')
    await tabButtons().filter((b) => b.text() === '预览')[0].trigger('click')
    expect(wrapper.find('.lesson-content').html()).not.toContain('<script>')
    expect(wrapper.find('.lesson-content').text()).toContain('正文')
  })

  it('保存成功后快照重置，状态回到已保存', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    await wrapper.find('.content-textarea').setValue('改动')
    expect(wrapper.find('.save-state').text()).toBe('未保存')
    await wrapper.find('.save-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.save-state').text()).toBe('已保存')
    expect(routerState.leaveHook({}, {})).toBe(true)
  })

  it('草稿课时显示「发布」，点击提交内容+status 并 toast', async () => {
    coursesAPI.getChapters.mockResolvedValue({
      data: [{ id: 11, lessons: [{ id: 2, title: '讲义一课', content_type: 'markdown', content: '正文', status: 'draft' }] }],
    })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    const publishBtn = wrapper.find('.publish-btn')
    expect(publishBtn.exists()).toBe(true)
    expect(publishBtn.text()).toBe('发布')
    await publishBtn.trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '讲义一课',
      content: '正文',
      status: 'published',
    })
    expect(appState.showToast).toHaveBeenCalledWith('课时已发布', 'success')
    expect(wrapper.find('.publish-btn').text()).toBe('转为草稿')
  })

  it('已发布课时显示「转为草稿」，点击提交 status:draft', async () => {
    coursesAPI.getChapters.mockResolvedValue({
      data: [{ id: 11, lessons: [{ id: 2, title: '讲义一课', content_type: 'markdown', content: '正文', status: 'published' }] }],
    })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    expect(wrapper.find('.publish-btn').text()).toBe('转为草稿')
    await wrapper.find('.publish-btn').trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '讲义一课',
      content: '正文',
      status: 'draft',
    })
    expect(appState.showToast).toHaveBeenCalledWith('课时已转为草稿', 'success')
  })

  it('有未保存修改时发布：内容一并提交且快照重置', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    await wrapper.find('.content-textarea').setValue('改动后正文')
    expect(wrapper.find('.save-state').text()).toBe('未保存')
    await wrapper.find('.publish-btn').trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '讲义一课',
      content: '改动后正文',
      status: 'published',
    })
    // 发布成功：快照重置，未保存状态消失
    expect(wrapper.find('.save-state').text()).toBe('已保存')
    expect(routerState.leaveHook({}, {})).toBe(true)
  })

  it('发布失败 toast 错误且快照不重置', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    coursesAPI.updateLesson.mockRejectedValue({})
    const wrapper = await mountEditor()
    await wrapper.find('.content-textarea').setValue('改动后正文')
    await wrapper.find('.publish-btn').trigger('click')
    await flushPromises()
    expect(appState.showToast).toHaveBeenCalledWith('发布失败，请重试', 'error')
    expect(wrapper.find('.save-state').text()).toBe('未保存')
    expect(wrapper.find('.publish-btn').text()).toBe('发布')
  })
})
