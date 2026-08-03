// AppIcon 语义图标：本地 Iconify 数据、无 API 依赖、可访问性语义
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AppIcon from '../AppIcon.vue'

// 五个目标屏幕使用的全部语义键（与 AppIcon 内部 map 对齐）
const SEMANTIC_KEYS = [
  'home',
  'course',
  'assignment',
  'code',
  'exam',
  'experiment',
  'notification',
  'search',
  'calendar',
  'clock',
  'check',
  'close',
  'warning',
  'arrow-right',
  'chevron-right',
  'chevron-down',
  'book',
  'clipboard',
  'chart',
  'user',
  'logout',
  'more',
  'python',
  'plus',
  'settings',
  'edit',
  'eye',
  'copy',
]

describe('AppIcon', () => {
  it('为每个语义键渲染真实 SVG', () => {
    for (const name of SEMANTIC_KEYS) {
      const wrapper = mount(AppIcon, { props: { name } })
      const svg = wrapper.find('svg')
      expect(svg.exists(), `语义键 ${name} 应渲染 svg`).toBe(true)
    }
  })

  it('未提供 label 时图标对辅助技术隐藏', () => {
    const wrapper = mount(AppIcon, { props: { name: 'home' } })
    expect(wrapper.find('svg').attributes('aria-hidden')).toBe('true')
    expect(wrapper.attributes('role')).toBeUndefined()
  })

  it('提供 label 时暴露可访问图像语义', () => {
    const wrapper = mount(AppIcon, { props: { name: 'home', label: '返回首页' } })
    const svg = wrapper.find('svg')
    expect(svg.attributes('role')).toBe('img')
    expect(svg.attributes('aria-label')).toBe('返回首页')
    // Iconify 收到 aria-hidden="false" 时移除该属性，图标不再对辅助技术隐藏
    expect(svg.attributes('aria-hidden')).toBeUndefined()
  })

  it('支持数字与字符串尺寸', () => {
    const byNum = mount(AppIcon, { props: { name: 'home', size: 24 } })
    expect(byNum.find('svg').attributes('width')).toBe('24')
    const byStr = mount(AppIcon, { props: { name: 'home', size: '1.25em' } })
    expect(byStr.find('svg').attributes('width')).toBe('1.25em')
  })

  it('未知图标名渲染空并在开发环境告警', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const wrapper = mount(AppIcon, { props: { name: 'not-a-real-icon' } })
    expect(wrapper.find('svg').exists()).toBe(false)
    expect(warnSpy).toHaveBeenCalled()
    warnSpy.mockRestore()
  })
})
