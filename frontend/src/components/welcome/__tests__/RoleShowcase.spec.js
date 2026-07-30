import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import RoleShowcase from '../RoleShowcase.vue'
import { roles } from '../../../views/welcome/welcomeContent.js'

describe('RoleShowcase', () => {
  it('renders section title', () => {
    const wrapper = mount(RoleShowcase)
    expect(wrapper.text()).toContain('为每一位参与者设计')
  })

  it('renders all 4 role cards', () => {
    const wrapper = mount(RoleShowcase)
    const cards = wrapper.findAll('.role-card')
    expect(cards.length).toBe(roles.length)
  })

  it('each role card shows its title', () => {
    const wrapper = mount(RoleShowcase)
    for (const role of roles) {
      expect(wrapper.text()).toContain(role.title)
    }
  })

  it('activates card on hover', async () => {
    const wrapper = mount(RoleShowcase)
    const card = wrapper.find('.role-card')
    await card.trigger('mouseenter')
    expect(card.classes()).toContain('hovered')
  })
})
