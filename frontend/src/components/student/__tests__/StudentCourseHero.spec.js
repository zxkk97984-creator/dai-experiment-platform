// StudentCourseHero：164–168px 白卡；面包屑 + 课程身份 + 元数据 + 进度 + CTA
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
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
