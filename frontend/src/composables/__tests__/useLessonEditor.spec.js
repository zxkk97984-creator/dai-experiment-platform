// useLessonEditor：课时编辑页共享逻辑（加载/保存/离开守卫/beforeunload）
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { useLessonEditor } from '../useLessonEditor.js'

// 参照 NotebookPlayer.spec.js 惯例：vi.hoisted 捕获路由钩子与 mock 引用
const routerState = vi.hoisted(() => ({
  push: vi.fn(),
  leaveHook: null,
}))
const appState = vi.hoisted(() => ({
  showToast: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerState.push }),
  onBeforeRouteLeave: (hook) => {
    routerState.leaveHook = hook
  },
}))

vi.mock('../../api/courses.js', () => ({
  coursesAPI: {
    getChapters: vi.fn(),
    updateLesson: vi.fn(),
  },
}))

vi.mock('../../stores/app.js', () => ({
  useAppStore: () => appState,
}))

import { coursesAPI } from '../../api/courses.js'

// 跟踪全部挂载实例，测试间统一卸载（避免 beforeunload 监听在 window 上累积）
const mountedWrappers = []

// dirty 开关：测试中通过闭包变量控制 isDirty 返回值
let dirty

function mountEditor() {
  let result
  const Comp = defineComponent({
    setup() {
      result = useLessonEditor({
        courseId: 1,
        lessonId: 2,
        backPath: '/teacher/courses/1',
        isDirty: () => dirty,
        buildPayload: (lesson) => ({ title: lesson.title }),
      })
      return () => h('div')
    },
  })
  const wrapper = mount(Comp)
  mountedWrappers.push(wrapper)
  return { wrapper, result }
}

const chaptersResponse = [
  { id: 1, title: '第一章', lessons: [{ id: 2, title: '原标题', content_type: 'markdown', content: '正文' }] },
]

describe('useLessonEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routerState.leaveHook = null
    dirty = false
  })

  afterEach(() => {
    for (const wrapper of mountedWrappers.splice(0)) {
      wrapper.unmount()
    }
  })

  describe('load()', () => {
    it('通过 getChapters 过滤出目标课时', async () => {
      coursesAPI.getChapters.mockResolvedValue({ data: chaptersResponse })
      const { result } = mountEditor()
      expect(result.loading.value).toBe(true)
      await result.load()
      expect(coursesAPI.getChapters).toHaveBeenCalledWith(1)
      expect(result.lesson.value.title).toBe('原标题')
      expect(result.loading.value).toBe(false)
      expect(result.loadError.value).toBe('')
    })

    it('兼容 { items: [...] } 分页结构', async () => {
      coursesAPI.getChapters.mockResolvedValue({ data: { items: chaptersResponse } })
      const { result } = mountEditor()
      await result.load()
      expect(result.lesson.value.id).toBe(2)
    })

    it('课时不存在时置错误态', async () => {
      coursesAPI.getChapters.mockResolvedValue({ data: [{ id: 1, lessons: [{ id: 99 }] }] })
      const { result } = mountEditor()
      await result.load()
      expect(result.loadError.value).toBe('课时不存在或已被删除')
      expect(result.lesson.value).toBeNull()
    })

    it('接口失败时置错误态', async () => {
      coursesAPI.getChapters.mockRejectedValue(new Error('网络错误'))
      const { result } = mountEditor()
      await result.load()
      expect(result.loadError.value).toBe('课时加载失败，请稍后重试')
    })
  })

  describe('save()', () => {
    it('保存成功调用 updateLesson 并 toast', async () => {
      coursesAPI.getChapters.mockResolvedValue({ data: chaptersResponse })
      coursesAPI.updateLesson.mockResolvedValue({})
      const { result } = mountEditor()
      await result.load()
      await result.save()
      expect(coursesAPI.updateLesson).toHaveBeenCalledWith(2, { title: '原标题' })
      expect(appState.showToast).toHaveBeenCalledWith('课时已保存', 'success')
      expect(result.saving.value).toBe(false)
    })

    it('保存失败 toast 错误且不抛异常', async () => {
      coursesAPI.getChapters.mockResolvedValue({ data: chaptersResponse })
      coursesAPI.updateLesson.mockRejectedValue(new Error('500'))
      const { result } = mountEditor()
      await result.load()
      await result.save()
      expect(appState.showToast).toHaveBeenCalledWith('保存失败，请重试', 'error')
      expect(result.saving.value).toBe(false)
    })
  })

  describe('离开守卫', () => {
    it('未修改时直接放行', () => {
      const { result } = mountEditor()
      const ret = routerState.leaveHook({}, {})
      expect(ret).toBe(true)
      expect(result.showLeaveDialog.value).toBe(false)
    })

    it('有修改时拦截并弹出自定义确认框', () => {
      dirty = true
      const { result } = mountEditor()
      const ret = routerState.leaveHook({}, {})
      expect(ret).toBeInstanceOf(Promise)
      expect(result.showLeaveDialog.value).toBe(true)
    })

    it('确认离开 resolve(true) 并关闭弹窗', async () => {
      dirty = true
      const { result } = mountEditor()
      const ret = routerState.leaveHook({}, {})
      result.onConfirmLeave()
      await flushPromises()
      expect(await ret).toBe(true)
      expect(result.showLeaveDialog.value).toBe(false)
    })

    it('取消离开 resolve(false) 留在页面', async () => {
      dirty = true
      const { result } = mountEditor()
      const ret = routerState.leaveHook({}, {})
      result.onCancelLeave()
      await flushPromises()
      expect(await ret).toBe(false)
      expect(result.showLeaveDialog.value).toBe(false)
    })

    it('确认后再次导航直接放行（confirmedLeave 一次生效）', async () => {
      dirty = true
      const { result } = mountEditor()
      const ret = routerState.leaveHook({}, {})
      result.onConfirmLeave()
      await flushPromises()
      await ret
      expect(routerState.leaveHook({}, {})).toBe(true)
    })

    it('双击确认按钮只 resolve 一次（resolver 置 null 防重复）', async () => {
      dirty = true
      const { result } = mountEditor()
      const ret = routerState.leaveHook({}, {})
      result.onConfirmLeave()
      result.onConfirmLeave() // 第二次调用应被忽略
      await flushPromises()
      expect(await ret).toBe(true)
      // 弹窗已关闭，且没有二次弹窗
      expect(result.showLeaveDialog.value).toBe(false)
    })

    it('取消后再导航重新拦截（resolver 已清理可重新挂起）', async () => {
      dirty = true
      const { result } = mountEditor()
      const ret1 = routerState.leaveHook({}, {})
      result.onCancelLeave()
      await flushPromises()
      expect(await ret1).toBe(false)
      // 再次触发导航 → 新 Promise + 弹窗再次出现
      const ret2 = routerState.leaveHook({}, {})
      expect(ret2).toBeInstanceOf(Promise)
      expect(result.showLeaveDialog.value).toBe(true)
    })
  })

  describe('saveState 状态文字', () => {
    it('未修改时显示已保存', async () => {
      coursesAPI.getChapters.mockResolvedValue({ data: chaptersResponse })
      const { result } = mountEditor()
      await result.load()
      expect(result.saveState.value).toBe('已保存')
    })

    it('修改后显示未保存', async () => {
      coursesAPI.getChapters.mockResolvedValue({ data: chaptersResponse })
      dirty = true
      const { result } = mountEditor()
      await result.load()
      expect(result.saveState.value).toBe('未保存')
    })

    it('保存中显示保存中…', async () => {
      coursesAPI.getChapters.mockResolvedValue({ data: chaptersResponse })
      coursesAPI.updateLesson.mockResolvedValue({})
      const { result } = mountEditor()
      await result.load()
      const p = result.save()
      expect(result.saveState.value).toBe('保存中…')
      await p
      expect(result.saveState.value).toBe('已保存')
    })
  })

  describe('beforeunload 守卫', () => {
    it('有修改时 preventDefault 触发浏览器确认', async () => {
      coursesAPI.getChapters.mockResolvedValue({ data: chaptersResponse })
      dirty = true
      const { result } = mountEditor()
      await result.load()
      const evt = new Event('beforeunload')
      const preventSpy = vi.spyOn(evt, 'preventDefault')
      window.dispatchEvent(evt)
      expect(preventSpy).toHaveBeenCalled()
    })

    it('无修改时不拦截', async () => {
      coursesAPI.getChapters.mockResolvedValue({ data: chaptersResponse })
      const { result } = mountEditor()
      await result.load()
      const evt = new Event('beforeunload')
      const preventSpy = vi.spyOn(evt, 'preventDefault')
      window.dispatchEvent(evt)
      expect(preventSpy).not.toHaveBeenCalled()
    })

    it('组件卸载时移除监听', () => {
      const addSpy = vi.spyOn(window, 'addEventListener')
      const removeSpy = vi.spyOn(window, 'removeEventListener')
      const { wrapper } = mountEditor()
      expect(addSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function))
      wrapper.unmount()
      expect(removeSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function))
    })
  })
})
