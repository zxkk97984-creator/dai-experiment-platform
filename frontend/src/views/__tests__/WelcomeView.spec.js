import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import WelcomeView from '../WelcomeView.vue'

describe('WelcomeView', () => {
  async function mountView() {
    const router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', name: 'welcome', component: WelcomeView },
        { path: '/login', name: 'login', component: { template: '<div>Login</div>' } },
      ],
    })
    router.push('/')
    await router.isReady()

    return mount(WelcomeView, {
      global: {
        plugins: [router],
        stubs: {
          WelcomeHero: { template: '<section class="hero-stub"><button class="hero-btn-primary">Explore</button><button class="hero-btn-secondary">Login</button></section>' },
          CapabilityShowcase: { template: '<section class="cap-stub">Capabilities</section>' },
          LearningFlow: { template: '<section class="loop-stub">Flow</section>', props: ['steps', 'isVisible'] },
          RoleShowcase: { template: '<section class="role-stub">Roles</section>' },
        },
      },
    })
  }

  it('renders the welcome page wrapper', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('.welcome-page').exists()).toBe(true)
  })

  it('renders the sticky navigation', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('.w-nav').exists()).toBe(true)
  })

  it('renders the brand element', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('.w-nav-brand').exists()).toBe(true)
  })

  it('renders the login button', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('.w-nav-login').exists()).toBe(true)
  })

  it('renders all four section stubs', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('.hero-stub').exists()).toBe(true)
    expect(wrapper.find('.cap-stub').exists()).toBe(true)
    expect(wrapper.find('.loop-stub').exists()).toBe(true)
    expect(wrapper.find('.role-stub').exists()).toBe(true)
  })

  it('navigates to /login when login button clicked', async () => {
    const wrapper = await mountView()
    const btn = wrapper.find('.w-nav-login')
    expect(btn.exists()).toBe(true)
    await btn.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(r => setTimeout(r, 50))
    expect(wrapper.vm.$router.currentRoute.value.path).toBe('/login')
  })
})
