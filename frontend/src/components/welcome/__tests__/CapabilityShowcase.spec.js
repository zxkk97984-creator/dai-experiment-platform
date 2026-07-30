import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CapabilityShowcase from '../CapabilityShowcase.vue'
import { capabilities } from '../../../views/welcome/welcomeContent.js'

describe('CapabilityShowcase', () => {
  it('renders section title', () => {
    const wrapper = mount(CapabilityShowcase)
    expect(wrapper.text()).toContain('覆盖完整 AI 学习与实验流程')
  })

  it('renders all capability cards', () => {
    const wrapper = mount(CapabilityShowcase)
    const cards = wrapper.findAll('.cap-card')
    expect(cards.length).toBe(capabilities.length)
  })

  it('each card shows its title', () => {
    const wrapper = mount(CapabilityShowcase)
    for (const cap of capabilities) {
      expect(wrapper.text()).toContain(cap.title)
    }
  })

  it('adds hover class on mouseenter', async () => {
    const wrapper = mount(CapabilityShowcase)
    const card = wrapper.find('.cap-card')
    await card.trigger('mouseenter')
    expect(card.classes()).toContain('hovered')
  })
})
