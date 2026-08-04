// StudioEditor：dirty 离开守卫（自定义确认弹窗）、返回按钮 backTo/router.back 两态
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import StudioEditor from '../StudioEditor.vue'

const routerState = vi.hoisted(() => ({
  push: vi.fn(),
  back: vi.fn(),
  leaveHook: null,
}))
const appState = vi.hoisted(() => ({ showToast: vi.fn() }))

// 可变 store：测试中直接修改 dirty/conflict 等字段
const storeState = vi.hoisted(() => ({
  name: '测试模板',
  description: '',
  draftRevision: 1,
  dirty: false,
  saving: false,
  conflict: false,
  conflictMessage: '',
  studentPreview: false,
  sortedCells: [],
  cells: [],
  runningCellId: null,
  open: vi.fn().mockResolvedValue(),
  destroy: vi.fn(),
  saveDraft: vi.fn(),
  publish: vi.fn(),
  importExisting: vi.fn(),
  exportDraft: vi.fn(),
  exportVersion: vi.fn(),
  previewRun: vi.fn(),
  updateCellSource: vi.fn(),
  addCell: vi.fn(),
  moveCell: vi.fn(),
  duplicateCell: vi.fn(),
  deleteCell: vi.fn(),
  setCellEditable: vi.fn(),
  setCellHidden: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerState.push, back: routerState.back }),
  onBeforeRouteLeave: (hook) => {
    routerState.leaveHook = hook
  },
}))

vi.mock('../../../stores/studio.js', () => ({
  useStudioStore: () => storeState,
}))

vi.mock('../../../stores/app.js', () => ({
  useAppStore: () => appState,
}))

const CellStubs = {
  CodeCell: { name: 'CodeCell', template: '<div class="code-cell-stub" />' },
  MarkdownCell: { name: 'MarkdownCell', template: '<div class="md-cell-stub" />' },
}

const mountedWrappers = []

async function mountEditor(props = {}) {
  const wrapper = mount(StudioEditor, {
    props: { templateId: '5', ...props },
    global: { stubs: CellStubs },
  })
  await flushPromises()
  mountedWrappers.push(wrapper)
  return wrapper
}

describe('StudioEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    routerState.leaveHook = null
    storeState.dirty = false
    storeState.conflict = false
    storeState.open.mockResolvedValue()
  })

  afterEach(() => {
    for (const wrapper of mountedWrappers.splice(0)) {
      wrapper.unmount()
    }
  })

  describe('未保存离开守卫', () => {
    it('dirty 时拦截并弹自定义确认框', async () => {
      storeState.dirty = true
      const wrapper = await mountEditor()
      const ret = routerState.leaveHook({}, {})
      expect(ret).toBeInstanceOf(Promise)
      await flushPromises()
      expect(wrapper.text()).toContain('有未保存的修改')
    })

    it('确认离开 → resolve(true) 并 destroy', async () => {
      storeState.dirty = true
      const wrapper = await mountEditor()
      const ret = routerState.leaveHook({}, {})
      await flushPromises()
      await wrapper.findAll('button').find((b) => b.text() === '离开').trigger('click')
      await flushPromises()
      expect(await ret).toBe(true)
      expect(storeState.destroy).toHaveBeenCalled()
    })

    it('取消离开 → resolve(false) 不 destroy', async () => {
      storeState.dirty = true
      const wrapper = await mountEditor()
      const ret = routerState.leaveHook({}, {})
      await flushPromises()
      await wrapper.findAll('button').find((b) => b.text() === '取消').trigger('click')
      await flushPromises()
      expect(await ret).toBe(false)
      expect(storeState.destroy).not.toHaveBeenCalled()
    })

    it('conflict 时不拦截，直接放行', async () => {
      storeState.dirty = true
      storeState.conflict = true
      await mountEditor()
      expect(routerState.leaveHook({}, {})).toBe(true)
    })

    it('不 dirty 直接放行并 destroy', async () => {
      await mountEditor()
      expect(routerState.leaveHook({}, {})).toBe(true)
      expect(storeState.destroy).toHaveBeenCalled()
    })

    it('确认离开后 beforeunload 放行（避免 router.back 双重确认）', async () => {
      storeState.dirty = true
      const wrapper = await mountEditor()
      const ret = routerState.leaveHook({}, {})
      await flushPromises()
      await wrapper.findAll('button').find((b) => b.text() === '离开').trigger('click')
      await flushPromises()
      expect(await ret).toBe(true)
      // confirmedLeave 置 true 后，beforeunload 不再 preventDefault
      const evt = new Event('beforeunload')
      const preventSpy = vi.spyOn(evt, 'preventDefault')
      window.dispatchEvent(evt)
      expect(preventSpy).not.toHaveBeenCalled()
    })
  })

  describe('返回按钮', () => {
    it('backTo 存在时 push 到目标路径', async () => {
      const wrapper = await mountEditor({ backTo: '/teacher/courses/1/manage' })
      await wrapper.findAll('button').find((b) => b.text().includes('返回')).trigger('click')
      expect(routerState.push).toHaveBeenCalledWith('/teacher/courses/1/manage')
      expect(routerState.back).not.toHaveBeenCalled()
    })

    it('无 backTo 且未修改时回退浏览器历史', async () => {
      const wrapper = await mountEditor()
      await wrapper.findAll('button').find((b) => b.text().includes('返回')).trigger('click')
      expect(routerState.back).toHaveBeenCalled()
      expect(routerState.push).not.toHaveBeenCalled()
    })

    it('无 backTo 且有修改时先弹自定义确认框，确认后 destroy 并 back', async () => {
      storeState.dirty = true
      const wrapper = await mountEditor()
      await wrapper.findAll('button').find((b) => b.text().includes('返回')).trigger('click')
      await flushPromises()
      // 弹确认框而非直接 back（router.back 不走路由守卫）
      expect(wrapper.text()).toContain('有未保存的修改')
      expect(routerState.back).not.toHaveBeenCalled()
      await wrapper.findAll('button').find((b) => b.text() === '离开').trigger('click')
      await flushPromises()
      expect(storeState.destroy).toHaveBeenCalled()
      expect(routerState.back).toHaveBeenCalled()
    })

    it('无 backTo 且有修改时取消不 back', async () => {
      storeState.dirty = true
      const wrapper = await mountEditor()
      await wrapper.findAll('button').find((b) => b.text().includes('返回')).trigger('click')
      await flushPromises()
      await wrapper.findAll('button').find((b) => b.text() === '取消').trigger('click')
      await flushPromises()
      expect(routerState.back).not.toHaveBeenCalled()
      expect(storeState.destroy).not.toHaveBeenCalled()
    })
  })
})
