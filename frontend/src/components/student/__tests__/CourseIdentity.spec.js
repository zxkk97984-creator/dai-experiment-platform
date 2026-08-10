// CourseIdentity：92–96px 浅色图标 tile；Python 品牌图标仅用于 Python 类课程，
// 其余用稳定关键词选择的库图标；禁止 emoji 图标。
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
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
    expect(wrapper.text()).not.toMatch(/[📚📗📘📙]/u)
    expect(wrapper.find('.course-identity__icon').exists()).toBe(true)
  })
})

describe('CourseIdentity 课程封面', () => {
  it('在正方形容器内完整显示课程封面', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/components/student/CourseIdentity.vue'), 'utf8')
    expect(source).toMatch(/\.course-identity__cover\s*\{[^}]*object-fit:\s*contain/s)
  })

  it('有封面 URL 时优先渲染封面图（94×94 占位）', () => {
    const wrapper = mount(CourseIdentity, {
      props: { title: 'Python 编程基础', coverUrl: '/api/v1/media/course-covers/42?v=x' },
    })
    const img = wrapper.find('.course-identity__cover')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('/api/v1/media/course-covers/42?v=x')
    expect(img.attributes('alt')).toBe('Python 编程基础课程封面')
    // 封面存在时不渲染语义图标
    expect(wrapper.find('.course-identity__icon').exists()).toBe(false)
  })

  it('无封面 URL 时保留现有语义图标占位', () => {
    const wrapper = mount(CourseIdentity, { props: { title: '机器学习导论' } })
    expect(wrapper.find('.course-identity__cover').exists()).toBe(false)
    expect(wrapper.find('.course-identity__icon').exists()).toBe(true)
  })

  it('图片加载失败后回退图标占位', async () => {
    const wrapper = mount(CourseIdentity, {
      props: { title: 'Python 编程基础', coverUrl: '/broken-cover.png' },
    })
    await wrapper.find('.course-identity__cover').trigger('error')
    expect(wrapper.find('.course-identity__cover').exists()).toBe(false)
    expect(wrapper.find('.course-identity__icon').exists()).toBe(true)
  })

  it('封面 URL 变化时重置失败状态并重新尝试', async () => {
    const wrapper = mount(CourseIdentity, {
      props: { title: 'Python 编程基础', coverUrl: '/broken-cover.png' },
    })
    await wrapper.find('.course-identity__cover').trigger('error')
    expect(wrapper.find('.course-identity__cover').exists()).toBe(false)

    await wrapper.setProps({ coverUrl: '/new-cover.png' })
    expect(wrapper.find('.course-identity__cover').exists()).toBe(true)
    expect(wrapper.find('.course-identity__cover').attributes('src')).toBe('/new-cover.png')
  })
})
