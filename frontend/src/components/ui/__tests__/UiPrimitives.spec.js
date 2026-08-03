// UI 原语：UiProgress / UiStatusPill / UiPanel 语义与插槽契约
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import UiPanel from '../UiPanel.vue'
import UiProgress from '../UiProgress.vue'
import UiStatusPill from '../UiStatusPill.vue'

describe('UiProgress', () => {
  it('将低于 0 的值钳制到 0', () => {
    const wrapper = mount(UiProgress, { props: { value: -20 } })
    expect(wrapper.find('.ui-progress__bar').attributes('style')).toContain('width: 0%')
    expect(wrapper.attributes('aria-valuenow')).toBe('0')
    expect(wrapper.attributes('aria-valuemin')).toBe('0')
    expect(wrapper.attributes('aria-valuemax')).toBe('100')
  })

  it('将高于 100 的值钳制到 100', () => {
    const wrapper = mount(UiProgress, { props: { value: 145 } })
    expect(wrapper.find('.ui-progress__bar').attributes('style')).toContain('width: 100%')
    expect(wrapper.attributes('aria-valuenow')).toBe('100')
  })

  it('正常值原样暴露', () => {
    const wrapper = mount(UiProgress, { props: { value: 42 } })
    expect(wrapper.attributes('aria-valuenow')).toBe('42')
    expect(wrapper.find('.ui-progress__bar').attributes('style')).toContain('width: 42%')
  })

  it('缺失或非法值视为 0 而非报错', () => {
    const wrapper = mount(UiProgress, { props: { value: null } })
    expect(wrapper.attributes('aria-valuenow')).toBe('0')
  })
})

describe('UiStatusPill', () => {
  const tones = {
    pending: 'pending',
    progress: 'progress',
    submitted: 'submitted',
    success: 'success',
    warning: 'warning',
    danger: 'danger',
    neutral: 'neutral',
  }

  it('覆盖全部七种语义色调', () => {
    for (const [tone, expected] of Object.entries(tones)) {
      const wrapper = mount(UiStatusPill, { props: { tone, label: '状态' } })
      expect(wrapper.classes()).toContain(`ui-status-${expected}`)
    }
  })

  it('未知色调回退到 neutral', () => {
    const wrapper = mount(UiStatusPill, { props: { tone: 'glowing-rainbow', label: 'x' } })
    expect(wrapper.classes()).toContain('ui-status-neutral')
  })

  it('展示文本内容', () => {
    const wrapper = mount(UiStatusPill, { props: { tone: 'success', label: '已通过' } })
    expect(wrapper.text()).toContain('已通过')
  })
})

describe('UiPanel', () => {
  it('暴露 header、default 与 footer 插槽', () => {
    const wrapper = mount(UiPanel, {
      slots: {
        header: '<h2 class="slot-h">面板标题</h2>',
        default: '<p class="slot-body">正文</p>',
        footer: '<div class="slot-f">页脚</div>',
      },
    })
    expect(wrapper.find('.slot-h').exists()).toBe(true)
    expect(wrapper.find('.slot-body').exists()).toBe(true)
    expect(wrapper.find('.slot-f').exists()).toBe(true)
  })

  it('单张白卡结构：class 带 ui-panel，无嵌套卡', () => {
    const wrapper = mount(UiPanel, { slots: { default: '<p>内容</p>' } })
    expect(wrapper.classes()).toContain('ui-panel')
    // 面板内部不应再出现 .card 类（嵌套卡）
    expect(wrapper.findAll('.card').length).toBe(0)
  })

  it('compact 模式切换紧凑间距', () => {
    const wrapper = mount(UiPanel, { props: { compact: true } })
    expect(wrapper.classes()).toContain('ui-panel--compact')
  })
})
