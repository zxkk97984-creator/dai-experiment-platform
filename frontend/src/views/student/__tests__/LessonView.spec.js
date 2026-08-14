// 学生课时页：本地视频播放器、外链按钮、错误态与重试
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// 每个测试结束后卸载组件，避免残留 watcher 监听共享路由状态
enableAutoUnmount(afterEach)

const routerState = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }))
const routeState = vi.hoisted(() => ({ params: { id: '7', lid: '701' } }))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  const { reactive } = await import('vue')
  // 路由参数使用 reactive 包装：测试中修改 paramsProxy 可触发组件内 watch
  const params = reactive(routeState.params)
  routeState.paramsProxy = params
  return {
    ...actual,
    useRouter: () => ({ push: routerState.push, replace: routerState.replace }),
    useRoute: () => ({ params, path: '/student/courses/7/lessons/701' }),
  }
})

const coursesMock = vi.hoisted(() => ({
  get: vi.fn(),
  getChapters: vi.fn(),
  getLessonVideoPlaybackUrl: vi.fn(),
}))
const toastMock = vi.hoisted(() => ({ showToast: vi.fn() }))

vi.mock('../../../api/courses.js', () => ({ coursesAPI: coursesMock }))
vi.mock('../../../stores/app.js', () => ({ useAppStore: () => toastMock }))
vi.mock('../../../components/common/CodeBlock.vue', () => ({
  default: { template: '<div class="code-block" />' },
}))

import LessonView from '../LessonView.vue'

const course = { id: 7, title: '机器学习导论', status: 'published' }

function videoLesson(overrides = {}) {
  return {
    id: 701,
    chapter_id: 70,
    title: '视频课',
    content_type: 'video',
    video_source: 'upload',
    video_url: null,
    video_filename: 'demo.mp4',
    video_size: 1024,
    ...overrides,
  }
}

async function mountPage(lessons) {
  coursesMock.get.mockResolvedValue({ data: course })
  coursesMock.getChapters.mockResolvedValue({
    data: [{ id: 70, title: '第一章', order_index: 0, lessons }],
  })
  const wrapper = mount(LessonView, {
    global: { stubs: { AppLayout: { template: '<div><slot /></div>' } } },
  })
  await flushPromises()
  return wrapper
}

describe('LessonView 本地视频播放', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    routeState.params.lid = '701'
  })

  it('本地来源调用播放 URL 接口并渲染带 controls 的 video', async () => {
    coursesMock.getLessonVideoPlaybackUrl.mockResolvedValue({
      data: { url: 'http://testserver/media?v=1' },
    })
    const wrapper = await mountPage([videoLesson()])

    expect(coursesMock.getLessonVideoPlaybackUrl).toHaveBeenCalledWith(701)
    const video = wrapper.find('video.lesson-video-player')
    expect(video.exists()).toBe(true)
    expect(video.attributes('controls')).toBeDefined()
    expect(video.attributes('src')).toBe('http://testserver/media?v=1')
  })

  it('外链来源不调用播放接口，仍渲染安全外链按钮', async () => {
    const wrapper = await mountPage([
      videoLesson({ video_source: 'external', video_url: 'https://v.example.com/x.mp4' }),
    ])

    expect(coursesMock.getLessonVideoPlaybackUrl).not.toHaveBeenCalled()
    const link = wrapper.find('a.btn-primary')
    expect(link.attributes('href')).toBe('https://v.example.com/x.mp4')
    expect(link.attributes('rel')).toBe('noopener noreferrer')
    expect(wrapper.find('video.lesson-video-player').exists()).toBe(false)
  })

  it('没有任何来源显示视频暂不可用', async () => {
    const wrapper = await mountPage([
      videoLesson({ video_source: 'external', video_url: null, video_filename: null }),
    ])
    expect(wrapper.text()).toContain('视频暂不可用')
  })

  it('播放 URL 加载失败显示明确错误与重新加载按钮', async () => {
    coursesMock.getLessonVideoPlaybackUrl.mockRejectedValue({ response: { status: 403 } })
    const wrapper = await mountPage([videoLesson()])

    expect(wrapper.find('.video-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('视频加载失败')

    // 手动重试成功
    coursesMock.getLessonVideoPlaybackUrl.mockResolvedValue({
      data: { url: 'http://testserver/media?v=2' },
    })
    const retryBtn = wrapper.findAll('.video-error button').find((b) => b.text().includes('重新加载视频'))
    await retryBtn.trigger('click')
    await flushPromises()
    expect(wrapper.find('video.lesson-video-player').attributes('src')).toBe('http://testserver/media?v=2')
  })

  it('媒体 error 仅自动重新获取一次签名地址，第二次显示错误', async () => {
    coursesMock.getLessonVideoPlaybackUrl.mockResolvedValue({
      data: { url: 'http://testserver/media?v=1' },
    })
    const wrapper = await mountPage([videoLesson()])

    // 第一次媒体错误：自动刷新一次
    await wrapper.find('video.lesson-video-player').trigger('error')
    await flushPromises()
    expect(coursesMock.getLessonVideoPlaybackUrl).toHaveBeenCalledTimes(2)

    // 第二次媒体错误：不再自动刷新，显示错误
    await wrapper.find('video.lesson-video-player').trigger('error')
    await flushPromises()
    expect(coursesMock.getLessonVideoPlaybackUrl).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.video-error').exists()).toBe(true)
  })

  it('路由切换课时后清空旧签名地址', async () => {
    coursesMock.getLessonVideoPlaybackUrl.mockResolvedValue({
      data: { url: 'http://testserver/media?v=old' },
    })
    const wrapper = await mountPage([
      videoLesson(),
      videoLesson({ id: 702, video_source: 'external', video_url: 'https://v.example.com/y.mp4' }),
    ])
    expect(wrapper.find('video.lesson-video-player').attributes('src')).toBe('http://testserver/media?v=old')

    // 切到外链课时：旧签名地址应被清空，且不为新课时请求播放地址
    routeState.paramsProxy.lid = '702'
    await flushPromises()
    expect(coursesMock.getLessonVideoPlaybackUrl).toHaveBeenCalledTimes(1)
    expect(wrapper.find('video.lesson-video-player').exists()).toBe(false)
    expect(wrapper.find('a.btn-primary').exists()).toBe(true)

    // 切回本地视频课时：重新获取签名
    routeState.paramsProxy.lid = '701'
    await flushPromises()
    expect(coursesMock.getLessonVideoPlaybackUrl).toHaveBeenCalledTimes(2)
    expect(wrapper.find('video.lesson-video-player').exists()).toBe(true)
  })

  it('组件卸载时清理待执行的 TOC 定时器', async () => {
    vi.useFakeTimers()
    const querySelectorAll = vi.spyOn(document, 'querySelectorAll')
    try {
      const wrapper = await mountPage([videoLesson({ content: '## 目录标题' })])
      expect(vi.getTimerCount()).toBeGreaterThan(0)

      querySelectorAll.mockClear()
      wrapper.unmount()
      vi.runAllTimers()

      expect(querySelectorAll).not.toHaveBeenCalledWith('.lesson-content')
    } finally {
      querySelectorAll.mockRestore()
      vi.clearAllTimers()
      vi.useRealTimers()
    }
  })

  it('在 nextTick 执行前卸载时不再创建 TOC 定时器', async () => {
    vi.useFakeTimers()
    const querySelectorAll = vi.spyOn(document, 'querySelectorAll')
    try {
      coursesMock.get.mockResolvedValue({ data: course })
      coursesMock.getChapters.mockResolvedValue({ data: [] })
      const wrapper = mount(LessonView, {
        global: { stubs: { AppLayout: { template: '<div><slot /></div>' } } },
      })

      wrapper.unmount()
      await flushPromises()
      vi.runAllTimers()

      expect(querySelectorAll).not.toHaveBeenCalledWith('.lesson-content')
    } finally {
      querySelectorAll.mockRestore()
      vi.clearAllTimers()
      vi.useRealTimers()
    }
  })
})
