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
