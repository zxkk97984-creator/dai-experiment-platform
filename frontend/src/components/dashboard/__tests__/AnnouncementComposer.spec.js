import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const createMock = vi.hoisted(() => ({ create: vi.fn() }))

vi.mock('../../../api/announcements.js', () => ({ announcementsAPI: createMock }))

import AnnouncementComposer from '../AnnouncementComposer.vue'

const courses = [{ id: 2, title: '机器学习导论' }, { id: 3, title: '深度学习实践' }]

function mountComposer() {
  // attachTo document.body：jsdom 焦点（document.activeElement）需要组件在 DOM 中
  return mount(AnnouncementComposer, { props: { courses }, attachTo: document.body })
}

function focusables(wrapper) {
  return wrapper
    .findAll('.composer-modal button, .composer-modal input, .composer-modal select, .composer-modal textarea')
    .filter((el) => el.attributes('disabled') === undefined)
}

beforeEach(() => {
  vi.clearAllMocks()
  createMock.create.mockReset()
  document.body.innerHTML = ''
})

describe('AnnouncementComposer', () => {
  it('挂载后标题输入框获得焦点', () => {
    const wrapper = mountComposer()
    const title = wrapper.get('.composer-form input[type="text"]')
    expect(document.activeElement).toBe(title.element)
  })

  it('Tab 在最后一个控件循环回第一个', async () => {
    const wrapper = mountComposer()
    const list = focusables(wrapper)
    const last = list[list.length - 1]
    const first = list[0]
    last.element.focus()
    await last.trigger('keydown', { key: 'Tab' })
    expect(document.activeElement).toBe(first.element)
  })

  it('Shift+Tab 在第一个控件循环到最后一个', async () => {
    const wrapper = mountComposer()
    const list = focusables(wrapper)
    const first = list[0]
    const last = list[list.length - 1]
    first.element.focus()
    await first.trigger('keydown', { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last.element)
  })

  it('Escape 关闭并 emit close', async () => {
    const wrapper = mountComposer()
    await wrapper.get('.composer-modal').trigger('keydown', { key: 'Escape' })
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('发布成功 emit published 并重置表单', async () => {
    createMock.create.mockResolvedValue({ data: { id: 99 } })
    const wrapper = mountComposer()
    await wrapper.get('.composer-form input[type="text"]').setValue('机房调整')
    await wrapper.get('.composer-form textarea').setValue('本周实验课调整到 A302。')
    await wrapper.get('.composer-form').trigger('submit')
    await flushPromises()
    expect(createMock.create).toHaveBeenCalledWith({
      title: '机房调整',
      content: '本周实验课调整到 A302。',
      priority: 'normal',
      scope: 'course',
      course_id: 2,
    })
    expect(wrapper.emitted('published')).toHaveLength(1)
    expect(wrapper.emitted('published')[0][0].id).toBe(99)
    expect(wrapper.get('.composer-form input[type="text"]').element.value).toBe('')
  })

  it('服务器错误保持对话框打开并展示错误', async () => {
    createMock.create.mockRejectedValue({ response: { data: { detail: { message: '发布失败' } } } })
    const wrapper = mountComposer()
    await wrapper.get('.composer-form input[type="text"]').setValue('机房调整')
    await wrapper.get('.composer-form textarea').setValue('内容')
    await wrapper.get('.composer-form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('发布失败')
    expect(wrapper.get('.composer-modal').exists()).toBe(true)
  })
})
