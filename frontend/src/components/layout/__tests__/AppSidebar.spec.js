import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AppSidebar from '../AppSidebar.vue'
import { useAuthStore } from '../../../stores/auth.js'

const routerState = vi.hoisted(() => ({
  push: vi.fn(),
  path: '/developer/templates',
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useRoute: () => ({ path: routerState.path }),
    useRouter: () => ({ push: routerState.push }),
  }
})

describe('AppSidebar 角色首页导航', () => {
  function mountAs(role, path) {
    routerState.path = path
    const pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore()
    auth.setUser({ id: 1, username: role, real_name: role, role })
    return { wrapper: mount(AppSidebar, { global: { plugins: [pinia] } }), auth }
  }

  beforeEach(() => {
    localStorage.clear()
    vi.resetAllMocks()
    setActivePinia(createPinia())
  })

  it('学生侧栏首个导航项为首页且根路由高亮', async () => {
    const { wrapper } = mountAs('student', '/student')
    const navItems = wrapper.findAll('.nav-item')
    expect(navItems[0].text()).toContain('首页')
    expect(navItems[0].classes()).toContain('active')
    await navItems[0].trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student')
  })

  it('学生首页项在子路由不高亮', () => {
    const { wrapper } = mountAs('student', '/student/courses')
    expect(wrapper.findAll('.nav-item')[0].classes()).not.toContain('active')
  })

  it('教师侧栏首个导航项为首页并指向 /teacher', async () => {
    const { wrapper } = mountAs('teacher', '/teacher')
    const navItems = wrapper.findAll('.nav-item')
    expect(navItems[0].text()).toContain('首页')
    expect(navItems[0].classes()).toContain('active')
    await navItems[0].trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/teacher')
  })

  it('教师首页项在子路由不高亮', () => {
    const { wrapper } = mountAs('teacher', '/teacher/courses')
    expect(wrapper.findAll('.nav-item')[0].classes()).not.toContain('active')
  })

  it('点击 logo 返回角色首页', async () => {
    const { wrapper } = mountAs('student', '/student/courses')
    await wrapper.get('.logo').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student')
  })

  it('logo 是真实 button 元素，原生键盘可聚焦并带可访问名称', async () => {
    const { wrapper } = mountAs('student', '/student')
    const logo = wrapper.get('.logo')
    expect(logo.element.tagName).toBe('BUTTON')
    expect(logo.attributes('type')).toBe('button')
    expect(logo.attributes('aria-label')).toBe('返回首页')
    // 原生 button：默认可获得键盘焦点（tabindex 无需手动设置）
    expect(logo.element.tabIndex).toBe(0)
    // 原生 button 支持回车/空格激活；点击行为与既有导航一致
    await logo.trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/student')
  })

  it('导航项始终提供可访问名称（图标栏下文本隐藏时依赖 aria-label）', () => {
    const { wrapper } = mountAs('teacher', '/teacher')
    const navItems = wrapper.findAll('.nav-item')
    expect(navItems.length).toBeGreaterThan(0)
    for (const item of navItems) {
      expect(item.attributes('aria-label')).toBeTruthy()
    }
    expect(navItems[0].attributes('aria-label')).toBe('首页')
    expect(navItems[1].attributes('aria-label')).toBe('课程')
  })

  it('/student/feedback 镜像参考图 01，高亮首页', () => {
    const { wrapper } = mountAs('student', '/student/feedback')
    const navItems = wrapper.findAll('.nav-item')
    expect(navItems[0].text()).toContain('首页')
    expect(navItems[0].classes()).toContain('active')
  })

  it('折叠按钮切换 collapsed 类并保留导航可访问名称', async () => {
    const { wrapper } = mountAs('student', '/student')
    const sidebar = wrapper.find('.sidebar')
    expect(sidebar.classes()).not.toContain('collapsed')
    await wrapper.get('.collapse-btn').trigger('click')
    expect(sidebar.classes()).toContain('collapsed')
    for (const item of wrapper.findAll('.nav-item')) {
      expect(item.attributes('aria-label')).toBeTruthy()
    }
  })
})

describe('AppSidebar developer navigation', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.resetAllMocks()
    setActivePinia(createPinia())
  })

  it('shows only the dedicated template workspace for a developer', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore()
    auth.setUser({
      id: 9,
      username: 'developer',
      real_name: 'Developer',
      role: 'developer',
    })
    const wrapper = mount(AppSidebar, {
      global: { plugins: [pinia] },
    })

    expect(wrapper.text()).toContain('实验模板')
    expect(wrapper.text()).not.toContain('作业')
    expect(wrapper.text()).not.toContain('考试')

    await wrapper.get('.nav-item').trigger('click')
    expect(routerState.push).toHaveBeenCalledWith('/developer/templates')
  })
})
