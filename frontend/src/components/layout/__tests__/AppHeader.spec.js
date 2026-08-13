// AppHeader：右侧用户菜单触发器；姓名 + 圆形头像 + chevron；键盘可访问下拉菜单
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AppHeader from '../AppHeader.vue'
import { useAuthStore } from '../../../stores/auth.js'

const routerState = vi.hoisted(() => ({ push: vi.fn() }))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useRouter: () => ({ push: routerState.push }),
  }
})

describe('AppHeader 用户菜单', () => {
  function mountAs(role = 'student', realName = '测试学生') {
    const pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore()
    auth.setUser({ id: 1, username: 'student_alice', real_name: realName, role })
    return { wrapper: mount(AppHeader, { global: { plugins: [pinia] }, attachTo: document.body }), auth }
  }

  beforeEach(() => {
    localStorage.clear()
    vi.resetAllMocks()
    setActivePinia(createPinia())
    document.body.innerHTML = ''
  })

  it('显示真实姓名、头像图标与下拉箭头', () => {
    const { wrapper } = mountAs('student', '测试学生')
    expect(wrapper.text()).toContain('测试学生')
    // 头像为库图标（user），不是首字母文本
    expect(wrapper.find('.user-avatar svg').exists()).toBe(true)
    // 下箭头 chevron
    expect(wrapper.find('.user-trigger svg').exists()).toBe(true)
  })

  it('点击触发器打开键盘可访问菜单', async () => {
    const { wrapper } = mountAs()
    const trigger = wrapper.get('.user-trigger')
    expect(trigger.attributes('aria-haspopup')).toBe('menu')
    expect(trigger.attributes('aria-expanded')).toBe('false')
    await trigger.trigger('click')
    expect(trigger.attributes('aria-expanded')).toBe('true')
    expect(wrapper.find('.user-menu').exists()).toBe(true)
    expect(wrapper.text()).toContain('测试学生')
    expect(wrapper.text()).toContain('学生')
  })

  it('Escape 关闭菜单', async () => {
    const { wrapper } = mountAs()
    await wrapper.get('.user-trigger').trigger('click')
    expect(wrapper.find('.user-menu').exists()).toBe(true)
    await wrapper.get('.user-trigger').trigger('keydown', { key: 'Escape' })
    expect(wrapper.find('.user-menu').exists()).toBe(false)
  })

  it('外部点击关闭菜单', async () => {
    const { wrapper } = mountAs()
    await wrapper.get('.user-trigger').trigger('click')
    expect(wrapper.find('.user-menu').exists()).toBe(true)
    document.dispatchEvent(new Event('pointerdown'))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.user-menu').exists()).toBe(false)
  })

  it('打开菜单后焦点移入首个菜单项（TASK-024）', async () => {
    const { wrapper } = mountAs()
    const trigger = wrapper.get('.user-trigger')
    trigger.element.focus()
    await trigger.trigger('click')
    await wrapper.vm.$nextTick()
    const logoutBtn = wrapper.findAll('.user-menu button').find((b) => b.text().includes('退出'))
    expect(document.activeElement).toBe(logoutBtn.element)
  })

  it('Escape 关闭菜单后焦点恢复到触发器（TASK-024）', async () => {
    const { wrapper } = mountAs()
    const trigger = wrapper.get('.user-trigger')
    trigger.element.focus()
    await trigger.trigger('click')
    await wrapper.vm.$nextTick()
    await trigger.trigger('keydown', { key: 'Escape' })
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.user-menu').exists()).toBe(false)
    expect(document.activeElement).toBe(trigger.element)
  })

  it('外部点击关闭菜单后焦点恢复到触发器（TASK-024）', async () => {
    const { wrapper } = mountAs()
    const trigger = wrapper.get('.user-trigger')
    trigger.element.focus()
    await trigger.trigger('click')
    await wrapper.vm.$nextTick()
    document.dispatchEvent(new Event('pointerdown'))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.user-menu').exists()).toBe(false)
    expect(document.activeElement).toBe(trigger.element)
  })

  it('保留原生 Tab/Enter/Space 按钮语义（TASK-024）', async () => {
    const { wrapper } = mountAs()
    const trigger = wrapper.get('.user-trigger')
    // 触发器为真实按钮，Enter/Space 的点击合成由浏览器原生处理，组件不拦截
    expect(trigger.element.tagName).toBe('BUTTON')
    expect(trigger.attributes('type')).toBe('button')
    await trigger.trigger('keydown', { key: 'Enter' })
    expect(trigger.attributes('aria-expanded')).toBe('false')
    await trigger.trigger('click')
    expect(trigger.attributes('aria-expanded')).toBe('true')
  })

  it('退出是唯一状态改变动作并路由到 /login', async () => {
    const { wrapper, auth } = mountAs()
    await wrapper.get('.user-trigger').trigger('click')
    const logoutSpy = vi.spyOn(auth, 'logout').mockImplementation(() => {})
    const logoutBtn = wrapper.findAll('.user-menu button').find((b) => b.text().includes('退出'))
    expect(logoutBtn).toBeTruthy()
    await logoutBtn.trigger('click')
    expect(logoutSpy).toHaveBeenCalled()
    expect(routerState.push).toHaveBeenCalledWith('/login')
  })
})
