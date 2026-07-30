import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WelcomeHero from '../WelcomeHero.vue'
import { heroContent } from '../../../views/welcome/welcomeContent.js'

describe('WelcomeHero', () => {
  it('renders hero copy', () => {
    const wrapper = mount(WelcomeHero, {
      props: { isVisible: false },
      global: { stubs: { 'svg': true } },
    })

    expect(wrapper.text()).toContain(heroContent.title)
    expect(wrapper.text()).toContain(heroContent.eyebrow)
    expect(wrapper.text()).toContain(heroContent.description)
  })

  it('renders both action buttons', () => {
    const wrapper = mount(WelcomeHero, {
      props: { isVisible: false },
      global: { stubs: { 'svg': true } },
    })

    const buttons = wrapper.findAll('button')
    expect(buttons.some(b => b.text().includes(heroContent.primaryAction))).toBe(true)
    expect(buttons.some(b => b.text().includes(heroContent.secondaryAction))).toBe(true)
  })

  it('emits explore when primary button is clicked', async () => {
    const wrapper = mount(WelcomeHero, {
      props: { isVisible: false },
      global: { stubs: { 'svg': true } },
    })

    const btn = wrapper.findAll('button').find(b => b.text().includes(heroContent.primaryAction))
    await btn.trigger('click')

    expect(wrapper.emitted('explore')).toBeTruthy()
  })

  it('emits login when secondary button is clicked', async () => {
    const wrapper = mount(WelcomeHero, {
      props: { isVisible: false },
      global: { stubs: { 'svg': true } },
    })

    const btn = wrapper.findAll('button').find(b => b.text().includes(heroContent.secondaryAction))
    await btn.trigger('click')

    expect(wrapper.emitted('login')).toBeTruthy()
  })

  it('renders code editor window', () => {
    const wrapper = mount(WelcomeHero, {
      props: { isVisible: false },
      global: { stubs: { 'svg': true } },
    })

    expect(wrapper.find('.code-window').exists()).toBe(true)
  })
})
