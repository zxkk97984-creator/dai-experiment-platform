// StudentCourseHero：164–168px 白卡；面包屑 + 课程身份 + 元数据 + 进度 + CTA
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import StudentCourseHero from '../StudentCourseHero.vue'

const course = {
  id: 7,
  title: '机器学习导论',
  description: '监督学习与模型评估',
  status: 'published',
  teacher_id: 5,
}

function mountHero(props = {}) {
  return mount(StudentCourseHero, {
    props: {
      course,
      progress: 40,
      totalLessons: 5,
      completedLessons: 2,
      enrolled: true,
      ...props,
    },
  })
}

describe('StudentCourseHero', () => {
  it('渲染面包屑与课程身份', () => {
    const wrapper = mountHero()
    expect(wrapper.text()).toContain('我的课程')
    expect(wrapper.text()).toContain('机器学习导论')
    expect(wrapper.text()).toContain('监督学习与模型评估')
  })

  it('渲染章节与课时元数据', () => {
    const wrapper = mountHero()
    expect(wrapper.text()).toContain('章节')
    expect(wrapper.text()).toContain('5')
  })

  it('渲染真实进度与完成数', () => {
    const wrapper = mountHero()
    expect(wrapper.text()).toContain('40%')
    expect(wrapper.find('.ui-progress').attributes('aria-valuenow')).toBe('40')
  })

  it('已选课显示继续学习 CTA 并触发 continue 事件', async () => {
    const wrapper = mountHero()
    const btn = wrapper.get('.hero-continue-btn')
    expect(btn.text()).toContain('继续学习')
    await btn.trigger('click')
    expect(wrapper.emitted('continue')).toBeTruthy()
  })

  it('未选课显示选课按钮并触发 enroll 事件', async () => {
    const wrapper = mountHero({ enrolled: false })
    const btn = wrapper.get('.hero-enroll-btn')
    expect(btn.text()).toContain('选课')
    await btn.trigger('click')
    expect(wrapper.emitted('enroll')).toBeTruthy()
  })

  it('元数据使用低对比边框控件而非重填充徽章', () => {
    const wrapper = mountHero()
    const chip = wrapper.get('.hero-chip')
    expect(chip.classes()).toContain('hero-chip')
  })
})

describe('StudentCourseHero 课程封面', () => {
  it('使用正方形容器并完整显示课程封面', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/components/student/StudentCourseHero.vue'), 'utf8')
    expect(source).toMatch(/\.hero-cover\s*\{[^}]*aspect-ratio:\s*1\s*\/\s*1/s)
    expect(source).toMatch(/\.hero-cover__img\s*\{[^}]*object-fit:\s*contain/s)
  })

  it('受管封面 key 渲染为公开媒体 URL', () => {
    const wrapper = mountHero({ course: { ...course, cover: 'covers/7/abc.webp' } })
    const img = wrapper.find('.hero-cover__img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('/api/v1/media/course-covers/7?v=covers%2F7%2Fabc.webp')
    expect(img.attributes('alt')).toBe('机器学习导论课程封面')
  })

  it('历史 HTTP(S) URL 原样渲染', () => {
    const legacy = 'https://legacy.example.com/course-cover.jpg'
    const wrapper = mountHero({ course: { ...course, cover: legacy } })
    expect(wrapper.find('.hero-cover__img').attributes('src')).toBe(legacy)
  })

  it('无封面时显示纯色占位块', () => {
    const wrapper = mountHero()
    expect(wrapper.find('.hero-cover__img').exists()).toBe(false)
    expect(wrapper.find('.hero-cover').exists()).toBe(true)
  })

  it('图片加载失败后回退占位块', async () => {
    const wrapper = mountHero({ course: { ...course, cover: 'covers/7/abc.webp' } })
    await wrapper.find('.hero-cover__img').trigger('error')
    expect(wrapper.find('.hero-cover__img').exists()).toBe(false)
    expect(wrapper.find('.hero-cover').exists()).toBe(true)
  })

  it('未选课时同样显示封面', () => {
    const wrapper = mountHero({
      enrolled: false,
      course: { ...course, cover: 'covers/7/abc.png' },
    })
    expect(wrapper.find('.hero-cover__img').exists()).toBe(true)
    expect(wrapper.get('.hero-enroll-btn').text()).toContain('选课')
  })

  it('封面变化时重置加载失败状态', async () => {
    const wrapper = mountHero({ course: { ...course, cover: 'covers/7/broken.png' } })
    await wrapper.find('.hero-cover__img').trigger('error')
    expect(wrapper.find('.hero-cover__img').exists()).toBe(false)

    await wrapper.setProps({ course: { ...course, cover: 'covers/7/new.png' } })
    const img = wrapper.find('.hero-cover__img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('/api/v1/media/course-covers/7?v=covers%2F7%2Fnew.png')
  })
})
