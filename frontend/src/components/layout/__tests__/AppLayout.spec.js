import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AppLayout from '../AppLayout.vue'
import { useAppStore } from '../../../stores/app.js'

vi.mock('../../../api/users.js', () => ({
  usersAPI: { getMyPreferences: vi.fn() },
}))

const SidebarStub = {
  props: ['variant', 'studentContext'],
  template: '<aside class="sidebar-stub" :data-variant="variant" :data-student-class="studentContext?.className" />',
}

const HeaderStub = {
  props: ['variant'],
  template: '<header class="header-stub" :data-variant="variant" />',
}

describe('AppLayout 学生工作台变体', () => {
  function mountLayout(props = {}) {
    const pinia = createPinia()
    setActivePinia(pinia)
    return {
      app: useAppStore(),
      wrapper: mount(AppLayout, {
        props,
        global: {
          plugins: [pinia],
          stubs: { AppSidebar: SidebarStub, AppHeader: HeaderStub },
        },
      }),
    }
  }

  beforeEach(() => {
    localStorage.clear()
    vi.resetAllMocks()
    setActivePinia(createPinia())
  })

  it('把 student-workspace 变体传给侧栏和顶栏，并忽略折叠状态', async () => {
    const { wrapper, app } = mountLayout({
      variant: 'student-workspace',
      studentContext: { className: '24621601班' },
    })
    app.sidebarCollapsed = true
    await wrapper.vm.$nextTick()

    expect(wrapper.get('.shell').classes()).toContain('student-workspace-shell')
    expect(wrapper.get('.shell').classes()).not.toContain('is-collapsed')
    expect(wrapper.get('.sidebar-stub').attributes('data-variant')).toBe('student-workspace')
    expect(wrapper.get('.sidebar-stub').attributes('data-student-class')).toBe('24621601班')
    expect(wrapper.get('.header-stub').attributes('data-variant')).toBe('student-workspace')
    expect(wrapper.find('.workspace-mobile-backdrop').exists()).toBe(true)

    app.mobileNavOpen = true
    await wrapper.vm.$nextTick()
    expect(wrapper.get('.shell').classes()).toContain('mobile-nav-open')
    await wrapper.get('.workspace-mobile-backdrop').trigger('click')
    expect(app.mobileNavOpen).toBe(false)
  })

  it('默认布局继续响应原有折叠状态且不渲染工作台遮罩', async () => {
    const { wrapper, app } = mountLayout()
    app.sidebarCollapsed = true
    await wrapper.vm.$nextTick()

    expect(wrapper.get('.shell').classes()).toContain('is-collapsed')
    expect(wrapper.get('.shell').classes()).not.toContain('student-workspace-shell')
    expect(wrapper.get('.sidebar-stub').attributes('data-variant')).toBe('default')
    expect(wrapper.get('.header-stub').attributes('data-variant')).toBe('default')
    expect(wrapper.find('.workspace-mobile-backdrop').exists()).toBe(false)
  })

  it('教师工作台复用工作台外壳并忽略折叠状态', async () => {
    const { wrapper, app } = mountLayout({ variant: 'teacher-workspace' })
    app.sidebarCollapsed = true
    await wrapper.vm.$nextTick()

    expect(wrapper.get('.shell').classes()).toContain('teacher-workspace-shell')
    expect(wrapper.get('.shell').classes()).not.toContain('is-collapsed')
    expect(wrapper.get('.sidebar-stub').attributes('data-variant')).toBe('teacher-workspace')
    expect(wrapper.get('.header-stub').attributes('data-variant')).toBe('teacher-workspace')
    expect(wrapper.find('.workspace-mobile-backdrop').exists()).toBe(true)
  })
})
