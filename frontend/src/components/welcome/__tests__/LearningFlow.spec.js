import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import LearningFlow from '../LearningFlow.vue'
import { learningSteps } from '../../../views/welcome/welcomeContent.js'

describe('LearningFlow', () => {
  it('renders section title', () => {
    const wrapper = mount(LearningFlow, {
      props: { steps: learningSteps, isVisible: false },
      global: { stubs: { 'svg': true } },
    })

    expect(wrapper.text()).toContain('学习闭环')
    expect(wrapper.text()).toContain('从选课到复盘')
  })

  it('renders all 5 learning steps when visible', () => {
    const wrapper = mount(LearningFlow, {
      props: { steps: learningSteps, isVisible: true },
      global: { stubs: { 'svg': true } },
    })

    const nodes = wrapper.findAll('.loop-node')
    expect(nodes.length).toBe(learningSteps.length)
  })

  it('each step shows its title', () => {
    const wrapper = mount(LearningFlow, {
      props: { steps: learningSteps, isVisible: true },
      global: { stubs: { 'svg': true } },
    })

    for (const step of learningSteps) {
      expect(wrapper.text()).toContain(step.title)
    }
  })

  it('applies visible class when isVisible is true', () => {
    const wrapper = mount(LearningFlow, {
      props: { steps: learningSteps, isVisible: true },
      global: { stubs: { 'svg': true } },
    })

    expect(wrapper.find('.learning-loop').classes()).toContain('loop--visible')
  })

  it('does not apply visible class when isVisible is false', () => {
    const wrapper = mount(LearningFlow, {
      props: { steps: learningSteps, isVisible: false },
      global: { stubs: { 'svg': true } },
    })

    expect(wrapper.find('.learning-loop').classes()).not.toContain('loop--visible')
  })

  it('renders a connecting rail', () => {
    const wrapper = mount(LearningFlow, {
      props: { steps: learningSteps, isVisible: true },
      global: { stubs: { 'svg': true } },
    })

    expect(wrapper.find('.loop-rail-fill').exists()).toBe(true)
  })
})
