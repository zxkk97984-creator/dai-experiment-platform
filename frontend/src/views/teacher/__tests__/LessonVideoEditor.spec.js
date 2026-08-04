// 视频编辑页：回填、保存 payload、video_url 空串归一 null、预览外链
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import LessonVideoEditor from '../LessonVideoEditor.vue'

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
  {
    id: 11,
    lessons: [{
      id: 2,
      title: '视频一课',
      content_type: 'video',
      content: '视频简介',
      video_url: 'https://example.com/a.mp4',
    }],
  },
]

async function mountEditor() {
  const wrapper = mount(LessonVideoEditor, {
    props: { courseId: '1', lessonId: '2', backPath: '/teacher/courses/1/manage' },
  })
  await flushPromises()
  return wrapper
}

describe('LessonVideoEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    routerState.leaveHook = null
  })

  it('回填标题、链接与简介', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    const wrapper = await mountEditor()
    expect(wrapper.find('.title-input').element.value).toBe('视频一课')
    expect(wrapper.find('#video-url').element.value).toBe('https://example.com/a.mp4')
    expect(wrapper.find('#video-desc').element.value).toBe('视频简介')
  })

  it('保存 payload：video_url 有值原样提交', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    await wrapper.find('#video-url').setValue('https://example.com/b.mp4')
    await wrapper.find('.save-btn').trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '视频一课',
      video_url: 'https://example.com/b.mp4',
      content: '视频简介',
    })
    expect(appState.showToast).toHaveBeenCalledWith('课时已保存', 'success')
  })

  it('video_url 空串归一 null', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    await wrapper.find('#video-url').setValue('   ')
    await wrapper.find('.save-btn').trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '视频一课',
      video_url: null,
      content: '视频简介',
    })
  })

  it('预览区显示外链', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    const wrapper = await mountEditor()
    expect(wrapper.find('.preview-pane a').attributes('href')).toBe('https://example.com/a.mp4')
    expect(wrapper.find('.preview-pane a').text()).toBe('https://example.com/a.mp4')
  })
})
