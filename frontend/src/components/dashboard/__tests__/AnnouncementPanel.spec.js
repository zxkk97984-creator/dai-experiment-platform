import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import AnnouncementPanel from '../AnnouncementPanel.vue'

const notice = (overrides = {}) => ({
  id: 1,
  title: '实验课机房调整',
  content: '本周实验课调整到 A302。',
  priority: 'important',
  scope: 'course',
  course_id: 2,
  course_title: '机器学习导论',
  author_name: '王老师',
  published_at: '2026-08-01T04:00:00Z',
  expires_at: null,
  is_read: false,
  ...overrides,
})

const baseProps = { announcements: [], loading: false, error: false, canPublish: false }

describe('AnnouncementPanel', () => {
  it('加载态展示占位并标记忙碌', () => {
    const wrapper = mount(AnnouncementPanel, {
      props: { ...baseProps, loading: true },
    })
    expect(wrapper.find('[aria-busy="true"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('加载中')
  })

  it('错误态可点击重试', async () => {
    const wrapper = mount(AnnouncementPanel, {
      props: { ...baseProps, error: true },
    })
    expect(wrapper.get('[role="alert"]').exists()).toBe(true)
    await wrapper.get('.retry-btn').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('空态如实展示无公告', () => {
    const wrapper = mount(AnnouncementPanel, { props: baseProps })
    expect(wrapper.text()).toContain('暂无公告')
  })

  it('有数据时展示标题、纯文本内容与课程来源', () => {
    const wrapper = mount(AnnouncementPanel, {
      props: { ...baseProps, announcements: [notice()] },
    })
    expect(wrapper.text()).toContain('实验课机房调整')
    expect(wrapper.text()).toContain('本周实验课调整到 A302。')
    expect(wrapper.text()).toContain('机器学习导论')
    // 内容按纯文本渲染，不含 HTML 标签
    expect(wrapper.find('.notice-content').html()).toContain('本周实验课调整到 A302。')
    expect(wrapper.find('.notice-content').html()).not.toContain('<p>')
    expect(wrapper.text()).toContain('王老师')
  })

  it('全局公告展示全局来源', () => {
    const wrapper = mount(AnnouncementPanel, {
      props: { ...baseProps, announcements: [notice({ scope: 'global', course_title: null })] },
    })
    expect(wrapper.text()).toContain('全局')
  })

  it('未读公告有标记，点击标记已读 emit mark-read 恰好一次', async () => {
    const wrapper = mount(AnnouncementPanel, {
      props: { ...baseProps, announcements: [notice()] },
    })
    expect(wrapper.find('.unread-dot').exists()).toBe(true)
    await wrapper.get('.mark-read-btn').trigger('click')
    expect(wrapper.emitted('mark-read')).toHaveLength(1)
    expect(wrapper.emitted('mark-read')[0][0].id).toBe(1)
  })

  it('已读公告无未读标记', () => {
    const wrapper = mount(AnnouncementPanel, {
      props: { ...baseProps, announcements: [notice({ is_read: true })] },
    })
    expect(wrapper.find('.unread-dot').exists()).toBe(false)
  })

  it('canPublish 时展示发布控件并 emit publish', async () => {
    const wrapper = mount(AnnouncementPanel, {
      props: { ...baseProps, canPublish: true },
    })
    await wrapper.get('.publish-btn').trigger('click')
    expect(wrapper.emitted('publish')).toHaveLength(1)
  })

  it('canPublish 为 false 时不展示发布控件', () => {
    const wrapper = mount(AnnouncementPanel, {
      props: { ...baseProps, canPublish: false },
    })
    expect(wrapper.find('.publish-btn').exists()).toBe(false)
  })
})
