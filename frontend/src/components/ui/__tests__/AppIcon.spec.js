// AppIcon 语义图标契约（TASK-025/F-29）：本地 Iconify 数据、无 API 依赖、可访问性语义
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AppIcon from '../AppIcon.vue'
import { ICONS } from '../icon-map.js'

// 契约：测试枚举映射模块的全部已声明语义键——新增/遗漏图标在此暴露
const ALL_KEYS = Object.keys(ICONS)

describe('AppIcon 图标契约', () => {
  it('为每个已声明语义键渲染真实 SVG', () => {
    expect(ALL_KEYS.length).toBeGreaterThan(0)
    for (const name of ALL_KEYS) {
      const wrapper = mount(AppIcon, { props: { name } })
      const svg = wrapper.find('svg')
      expect(svg.exists(), `语义键 ${name} 应渲染 svg`).toBe(true)
      expect(svg.attributes('data-set'), `语义键 ${name} 应声明来源图标集`).toBeTruthy()
    }
  })

  it('lock 映射存在且渲染（F-29：课程锁定课时）', () => {
    expect(ICONS.lock).toBeDefined()
    const wrapper = mount(AppIcon, { props: { name: 'lock' } })
    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.find('svg').attributes('data-set')).toBe('ri')
  })
})

describe('AppIcon 可访问性语义', () => {
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
})

describe('AppIcon 未知键', () => {
  it('未知图标名渲染空并在开发环境告警（生产保持安全 fallback）', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const wrapper = mount(AppIcon, { props: { name: 'not-a-real-icon' } })
    expect(wrapper.find('svg').exists()).toBe(false)
    expect(warnSpy).toHaveBeenCalled()
    warnSpy.mockRestore()
  })
})
