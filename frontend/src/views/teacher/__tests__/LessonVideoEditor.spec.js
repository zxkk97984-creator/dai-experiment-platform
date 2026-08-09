// 视频编辑页：回填、保存 payload、video_url 空串归一 null、预览外链、本地上传交互
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
    uploadLessonVideo: vi.fn(),
    deleteLessonVideo: vi.fn(),
    getLessonVideoPlaybackUrl: vi.fn(),
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

describe('LessonVideoEditor 本地上传', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    routerState.leaveHook = null
  })

  it('upload 来源回填：进入上传模式并请求播放地址', async () => {
    coursesAPI.getChapters.mockResolvedValue({
      data: [{
        id: 11,
        lessons: [{
          id: 2,
          title: '本地视频课',
          content_type: 'video',
          content: '',
          video_source: 'upload',
          video_url: null,
          video_filename: 'demo.mp4',
          video_size: 1024,
        }],
      }],
    })
    coursesAPI.getLessonVideoPlaybackUrl.mockResolvedValue({ data: { url: 'http://testserver/media?sig=x' } })
    const wrapper = await mountEditor()

    expect(wrapper.find('.source-tab.active').text()).toContain('上传视频文件')
    expect(coursesAPI.getLessonVideoPlaybackUrl).toHaveBeenCalledWith('2')
    expect(wrapper.find('video.video-player').attributes('src')).toBe('http://testserver/media?sig=x')
  })

  it('选择文件后立即上传，成功后显示文件名与播放器', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    const file = new File(['x'], 'demo.mp4', { type: 'video/mp4' })
    const uploadedLesson = {
      id: 2, title: '视频一课', content_type: 'video', content: '视频简介',
      video_source: 'upload', video_url: null, video_filename: 'demo.mp4', video_size: 1,
    }
    coursesAPI.uploadLessonVideo.mockResolvedValue({
      data: { lesson: uploadedLesson, playback_url: 'http://testserver/media?sig=y' },
    })
    const wrapper = await mountEditor()

    await wrapper.find('.source-tabs .source-tab:nth-child(2)').trigger('click')
    // jsdom 无法直接 setValue 文件输入，用 defineProperty 注入 files 后触发 change
    const input = wrapper.find('#video-file')
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
    await input.trigger('change')
    await flushPromises()

    expect(coursesAPI.uploadLessonVideo).toHaveBeenCalledWith('2', file, expect.objectContaining({
      onUploadProgress: expect.any(Function),
      signal: expect.anything(),
    }))
    expect(wrapper.text()).toContain('demo.mp4')
    expect(wrapper.find('video.video-player').attributes('src')).toBe('http://testserver/media?sig=y')
  })

  it('上传过程中显示进度并可取消', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    let resolveUpload
    coursesAPI.uploadLessonVideo.mockReturnValue(new Promise((resolve) => { resolveUpload = resolve }))
    const wrapper = await mountEditor()

    await wrapper.find('.source-tabs .source-tab:nth-child(2)').trigger('click')
    const input = wrapper.find('#video-file')
    Object.defineProperty(input.element, 'files', {
      value: [new File(['x'], 'demo.mp4', { type: 'video/mp4' })], configurable: true,
    })
    await input.trigger('change')
    await flushPromises()

    expect(wrapper.find('.cancel-btn').exists()).toBe(true)
    // 触发上传回调后取消
    const { onUploadProgress, signal } = coursesAPI.uploadLessonVideo.mock.calls[0][2]
    onUploadProgress({ loaded: 50, total: 100 })
    await flushPromises()
    expect(wrapper.text()).toContain('50%')
    expect(signal.aborted).toBe(false)
    signal.addEventListener('abort', () => {})
    await wrapper.find('.cancel-btn').trigger('click')
    expect(signal.aborted).toBe(true)
    resolveUpload?.(undefined)
    await flushPromises()
  })

  it('413 错误显示大小限制文案', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    coursesAPI.uploadLessonVideo.mockRejectedValue({ response: { status: 413 } })
    const wrapper = await mountEditor()
    await wrapper.find('.source-tabs .source-tab:nth-child(2)').trigger('click')
    const input = wrapper.find('#video-file')
    Object.defineProperty(input.element, 'files', {
      value: [new File(['x'], 'big.mp4', { type: 'video/mp4' })], configurable: true,
    })
    await input.trigger('change')
    await flushPromises()
    expect(wrapper.find('.upload-error').text()).toContain('500 MiB')
  })

  it('上传失败不清空原视频预览', async () => {
    coursesAPI.getChapters.mockResolvedValue({
      data: [{
        id: 11,
        lessons: [{
          id: 2, title: '本地视频课', content_type: 'video', content: '',
          video_source: 'upload', video_url: null, video_filename: 'old.mp4', video_size: 100,
        }],
      }],
    })
    coursesAPI.getLessonVideoPlaybackUrl.mockResolvedValue({ data: { url: 'http://testserver/old' } })
    coursesAPI.uploadLessonVideo.mockRejectedValue({ response: { status: 415 } })
    const wrapper = await mountEditor()
    expect(wrapper.find('video.video-player').exists()).toBe(true)

    const input = wrapper.find('#video-file')
    Object.defineProperty(input.element, 'files', {
      value: [new File(['x'], 'bad.mov', { type: 'video/quicktime' })], configurable: true,
    })
    await input.trigger('change')
    await flushPromises()
    expect(wrapper.find('.upload-error').exists()).toBe(true)
    expect(wrapper.find('video.video-player').exists()).toBe(true)
    expect(wrapper.text()).toContain('old.mp4')
  })

  it('上传来源保存标题/简介时不误传 video_url:null', async () => {
    coursesAPI.getChapters.mockResolvedValue({
      data: [{
        id: 11,
        lessons: [{
          id: 2, title: '本地视频课', content_type: 'video', content: '简介',
          video_source: 'upload', video_url: null, video_filename: 'old.mp4', video_size: 100,
        }],
      }],
    })
    coursesAPI.getLessonVideoPlaybackUrl.mockResolvedValue({ data: { url: 'http://testserver/old' } })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    await wrapper.find('.save-btn').trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '本地视频课',
      video_url: null,
      content: '简介',
    })
  })

  it('已有本地视频时填写外链保存需确认，确认后提交', async () => {
    coursesAPI.getChapters.mockResolvedValue({
      data: [{
        id: 11,
        lessons: [{
          id: 2, title: '本地视频课', content_type: 'video', content: '',
          video_source: 'upload', video_url: null, video_filename: 'old.mp4', video_size: 100,
        }],
      }],
    })
    coursesAPI.getLessonVideoPlaybackUrl.mockResolvedValue({ data: { url: 'http://testserver/old' } })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()

    // upload 来源下外链输入隐藏：先切回外链 tab 再填写
    await wrapper.find('.source-tabs .source-tab:nth-child(1)').trigger('click')
    await wrapper.find('#video-url').setValue('https://example.com/new.mp4')
    await wrapper.find('.save-btn').trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('切换后将删除已上传文件')

    await wrapper.find('.confirm-panel .btn-primary').trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '本地视频课',
      video_url: 'https://example.com/new.mp4',
      content: undefined,
    })
  })

  it('移除本地视频调用专用 DELETE 并回到外链模式', async () => {
    coursesAPI.getChapters.mockResolvedValue({
      data: [{
        id: 11,
        lessons: [{
          id: 2, title: '本地视频课', content_type: 'video', content: '',
          video_source: 'upload', video_url: null, video_filename: 'old.mp4', video_size: 100,
        }],
      }],
    })
    coursesAPI.getLessonVideoPlaybackUrl.mockResolvedValue({ data: { url: 'http://testserver/old' } })
    coursesAPI.deleteLessonVideo.mockResolvedValue({})
    const wrapper = await mountEditor()

    await wrapper.find('.remove-btn').trigger('click')
    await flushPromises()
    expect(coursesAPI.deleteLessonVideo).toHaveBeenCalledWith('2')
    expect(wrapper.find('.source-tab.active').text()).toContain('视频链接')
  })
})

describe('LessonVideoEditor 发布/转为草稿', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    routerState.leaveHook = null
  })

  it('草稿课时显示「发布」，点击提交内容+status 并 toast', async () => {
    coursesAPI.getChapters.mockResolvedValue({
      data: [{ id: 11, lessons: [{ id: 2, title: '视频一课', content_type: 'video', content: '简介', video_url: 'https://example.com/a.mp4', status: 'draft' }] }],
    })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    const publishBtn = wrapper.find('.publish-btn')
    expect(publishBtn.exists()).toBe(true)
    expect(publishBtn.text()).toBe('发布')
    await publishBtn.trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '视频一课',
      video_url: 'https://example.com/a.mp4',
      content: '简介',
      status: 'published',
    })
    expect(appState.showToast).toHaveBeenCalledWith('课时已发布', 'success')
    expect(wrapper.find('.publish-btn').text()).toBe('转为草稿')
  })

  it('已发布课时显示「转为草稿」，点击提交 status:draft', async () => {
    coursesAPI.getChapters.mockResolvedValue({
      data: [{ id: 11, lessons: [{ id: 2, title: '视频一课', content_type: 'video', content: '简介', video_url: 'https://example.com/a.mp4', status: 'published' }] }],
    })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    expect(wrapper.find('.publish-btn').text()).toBe('转为草稿')
    await wrapper.find('.publish-btn').trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '视频一课',
      video_url: 'https://example.com/a.mp4',
      content: '简介',
      status: 'draft',
    })
    expect(appState.showToast).toHaveBeenCalledWith('课时已转为草稿', 'success')
  })

  it('有未保存修改时发布：内容一并提交且快照重置', async () => {
    coursesAPI.getChapters.mockResolvedValue({ data: chapterResponse })
    coursesAPI.updateLesson.mockResolvedValue({})
    const wrapper = await mountEditor()
    await wrapper.find('#video-desc').setValue('新简介')
    expect(wrapper.find('.save-state').text()).toBe('未保存')
    await wrapper.find('.publish-btn').trigger('click')
    await flushPromises()
    expect(coursesAPI.updateLesson).toHaveBeenCalledWith('2', {
      title: '视频一课',
      video_url: 'https://example.com/a.mp4',
      content: '新简介',
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
    await wrapper.find('#video-desc').setValue('新简介')
    await wrapper.find('.publish-btn').trigger('click')
    await flushPromises()
    expect(appState.showToast).toHaveBeenCalledWith('发布失败，请重试', 'error')
    expect(wrapper.find('.save-state').text()).toBe('未保存')
    expect(wrapper.find('.publish-btn').text()).toBe('发布')
  })
})
