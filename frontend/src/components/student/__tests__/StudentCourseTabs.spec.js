// StudentCourseTabs：52px 水平条；激活项蓝色 2px 下划线；原生 button 键盘可操作
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StudentCourseTabs from '../StudentCourseTabs.vue'

describe('StudentCourseTabs', () => {
  it('渲染全部七个标签', () => {
    const wrapper = mount(StudentCourseTabs, { props: { active: 'overview' } })
    const labels = wrapper.findAll('.course-tab').map((t) => t.text())
    expect(labels).toEqual(['概览', '章节内容', '作业', '实验', '考试', '公告', '成绩'])
  })

  it('默认概览激活且无 pill 背景', () => {
    const wrapper = mount(StudentCourseTabs, { props: { active: 'overview' } })
    const active = wrapper.findAll('.course-tab').find((t) => t.text() === '概览')
    expect(active.classes()).toContain('active')
  })

  it('点击标签触发 change 并携带键名', async () => {
    const wrapper = mount(StudentCourseTabs, { props: { active: 'overview' } })
    const btn = wrapper.findAll('.course-tab').find((t) => t.text() === '作业')
    await btn.trigger('click')
    expect(wrapper.emitted('change')[0]).toEqual(['assignments'])
  })

  it('每个标签为原生 button，键盘可聚焦', () => {
    const wrapper = mount(StudentCourseTabs, { props: { active: 'overview' } })
    for (const tab of wrapper.findAll('.course-tab')) {
      expect(tab.element.tagName).toBe('BUTTON')
      expect(tab.element.tabIndex).toBe(0)
    }
  })

  it('激活项 aria-selected 正确', () => {
    const wrapper = mount(StudentCourseTabs, { props: { active: 'exams' } })
    const active = wrapper.findAll('.course-tab').find((t) => t.text() === '考试')
    expect(active.attributes('aria-selected')).toBe('true')
  })
})
