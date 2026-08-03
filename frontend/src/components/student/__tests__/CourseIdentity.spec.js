// CourseIdentity：92–96px 浅色图标 tile；Python 品牌图标仅用于 Python 类课程，
// 其余用稳定关键词选择的库图标；禁止 emoji 图标。
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CourseIdentity from '../CourseIdentity.vue'

describe('CourseIdentity', () => {
  it('Python 类标题使用 Python 品牌图标（logos 集）', () => {
    const wrapper = mount(CourseIdentity, { props: { title: 'Python 编程基础' } })
    const svg = wrapper.find('.course-identity__icon svg')
    expect(svg.exists()).toBe(true)
    expect(svg.attributes('data-set')).toBe('logos')
  })

  it('“Python 程序设计”等大小写变体同样识别', () => {
    const wrapper = mount(CourseIdentity, { props: { title: 'python 程序设计' } })
    expect(wrapper.find('svg').attributes('data-set')).toBe('logos')
  })

  it('数据类课程使用图表库图标（ri 集）', () => {
    const wrapper = mount(CourseIdentity, { props: { title: '机器学习导论' } })
    const svg = wrapper.find('svg')
    expect(svg.attributes('data-set')).toBe('ri')
    expect(svg.classes().join(' ')).not.toContain('iconify--logos')
  })

  it('未命中关键词时回退到通用课程图标', () => {
    const wrapper = mount(CourseIdentity, { props: { title: '量子物理学导论' } })
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('无插槽时渲染 meta prop', () => {
    const wrapper = mount(CourseIdentity, { props: { title: '数据结构', meta: '王老师' } })
    expect(wrapper.text()).toContain('数据结构')
    expect(wrapper.text()).toContain('王老师')
  })

  it('提供插槽时插槽内容优先于 meta prop', () => {
    const wrapper = mount(CourseIdentity, {
      props: { title: '数据结构', meta: '王老师' },
      slots: { default: '<span class="meta-slot">额外信息</span>' },
    })
    expect(wrapper.text()).toContain('数据结构')
    expect(wrapper.find('.meta-slot').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('王老师')
  })

  it('图标 tile 为浅色表面而非 emoji', () => {
    const wrapper = mount(CourseIdentity, { props: { title: 'Python 编程基础' } })
    expect(wrapper.text()).not.toMatch(/[📚📗📘📙]/)
    expect(wrapper.find('.course-identity__icon').exists()).toBe(true)
  })
})
