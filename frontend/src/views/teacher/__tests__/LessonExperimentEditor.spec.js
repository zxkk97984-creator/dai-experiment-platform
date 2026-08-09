// 普通实验编辑页：content 切分/拼接格式、保存 payload
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import LessonExperimentEditor from '../LessonExperimentEditor.vue'

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

function chapterWith(content) {
  return [{ id: 11, lessons: [{ id: 2, title: '实验一课', content_type: 'experiment', content }] }]
}

async function mountEditor() {
  const wrapper = mount(LessonExperimentEditor, {
    props: { courseId: '1', lessonId: '2', backPath: '/teacher/courses/1/manage' },
  })
  await flushPromises()
  return wrapper
}

describe('LessonExperimentEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    routerState.leaveHook = null
  })

  it('无标题头的老数据全文归实验任务描述框', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterWith('老数据正文\n第二行') })
    const wrapper = await mountEditor()
    expect(wrapper.find('#experiment-task').element.value).toBe('老数据正文\n第二行')
    expect(wrapper.find('#experiment-submission').element.value).toBe('')
  })

  it('含标题头时正确切分两框', async () => {
    coursesAPI.getChapters.mockResolvedValue({
      data: chapterWith('# 实验任务\n\n步骤一\n步骤二\n\n# 提交要求\n\n提交报告'),
    })
    const wrapper = await mountEditor()
    expect(wrapper.find('#experiment-task').element.value).toBe('步骤一\n步骤二')
    expect(wrapper.find('#experiment-submission').element.value).toBe('提交报告')
  })

  it('只有提交要求标题时，标题前内容归任务框', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterWith('前置说明\n\n# 提交要求\n\n交代码') })
    const wrapper = await mountEditor()
    expect(wrapper.find('#experiment-task').element.value).toBe('前置说明')
    expect(wrapper.find('#experiment-submission').element.value).toBe('交代码')
  })

  it('保存拼接为 # 实验任务 / # 提交要求 格式', async () => {
    coursesAPI.getChapters.mockResolvedValue({
      data: chapterWith('# 实验任务\n\n原任务\n\n# 提交要求\n\n原要求'),
    })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    await wrapper.find('#experiment-task').setValue('新任务')
    await wrapper.find('#experiment-submission').setValue('新要求')
    await wrapper.find('.save-btn').trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '实验一课',
      content: '# 实验任务\n\n新任务\n\n# 提交要求\n\n新要求',
    })
    expect(appState.showToast).toHaveBeenCalledWith('课时已保存', 'success')
  })

  it('预览模式渲染拼接后的 markdown', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterWith(undefined) })
    const wrapper = await mountEditor()
    await wrapper.find('#experiment-task').setValue('任务A')
    const previewBtn = wrapper.findAll('.mode-tabs button').find((b) => b.text() === '预览')
    await previewBtn.trigger('click')
    const html = wrapper.find('.lesson-content').html()
    expect(html).toContain('任务A')
    expect(html).toContain('提交要求')
  })

  it('草稿课时显示「发布」，点击提交内容+status 并 toast', async () => {
    coursesAPI.getChapters.mockResolvedValue({
      data: [{ id: 11, lessons: [{ id: 2, title: '实验一课', content_type: 'experiment', content: '# 实验任务\n\n任务A\n\n# 提交要求\n\n要求A', status: 'draft' }] }],
    })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    const publishBtn = wrapper.find('.publish-btn')
    expect(publishBtn.exists()).toBe(true)
    expect(publishBtn.text()).toBe('发布')
    await publishBtn.trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '实验一课',
      content: '# 实验任务\n\n任务A\n\n# 提交要求\n\n要求A',
      status: 'published',
    })
    expect(appState.showToast).toHaveBeenCalledWith('课时已发布', 'success')
    expect(wrapper.find('.publish-btn').text()).toBe('转为草稿')
  })

  it('已发布课时显示「转为草稿」，点击提交 status:draft', async () => {
    coursesAPI.getChapters.mockResolvedValue({
      data: [{ id: 11, lessons: [{ id: 2, title: '实验一课', content_type: 'experiment', content: '正文', status: 'published' }] }],
    })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    expect(wrapper.find('.publish-btn').text()).toBe('转为草稿')
    await wrapper.find('.publish-btn').trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '实验一课',
      content: '# 实验任务\n\n正文\n\n# 提交要求\n\n',
      status: 'draft',
    })
    expect(appState.showToast).toHaveBeenCalledWith('课时已转为草稿', 'success')
  })

  it('有未保存修改时发布：内容一并提交且快照重置', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterWith('# 实验任务\n\n原任务\n\n# 提交要求\n\n原要求') })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    await wrapper.find('#experiment-task').setValue('新任务')
    expect(wrapper.find('.save-state').text()).toBe('未保存')
    await wrapper.find('.publish-btn').trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '实验一课',
      content: '# 实验任务\n\n新任务\n\n# 提交要求\n\n原要求',
      status: 'published',
    })
    // 发布成功：快照重置，未保存状态消失
    expect(wrapper.find('.save-state').text()).toBe('已保存')
    expect(routerState.leaveHook({}, {})).toBe(true)
  })

  it('发布失败 toast 错误且快照不重置', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterWith('正文') })
    coursesAPI.updateLesson.mockRejectedValue({})
    const wrapper = await mountEditor()
    await wrapper.find('#experiment-task').setValue('改动')
    await wrapper.find('.publish-btn').trigger('click')
    await flushPromises()
    expect(appState.showToast).toHaveBeenCalledWith('发布失败，请重试', 'error')
    expect(wrapper.find('.save-state').text()).toBe('未保存')
    expect(wrapper.find('.publish-btn').text()).toBe('发布')
  })
})
