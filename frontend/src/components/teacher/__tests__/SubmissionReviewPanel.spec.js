/** SubmissionReviewPanel 评分工作台组件契约测试：回填、提交载荷与 saving 状态 */
import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SubmissionReviewPanel from '../SubmissionReviewPanel.vue'

function makeSubmission(overrides = {}) {
  return {
    id: 5,
    score: 85,
    feedback: '思路清晰，注意边界条件',
    reviewed_at: '2026-08-09T10:00:00Z',
    ...overrides,
  }
}

function mountPanel(props = {}) {
  return mount(SubmissionReviewPanel, {
    props: { submission: makeSubmission(), saving: false, ...props },
    global: { stubs: { AppIcon: { template: '<i class="icon-stub" />' } } },
  })
}

describe('SubmissionReviewPanel', () => {
  it('回填提交的分数与反馈', () => {
    const wrapper = mountPanel()
    expect(wrapper.get('#review-score').element.value).toBe('85')
    expect(wrapper.get('#review-feedback').element.value).toBe('思路清晰，注意边界条件')
  })

  it('提交时上抛规范化载荷', async () => {
    const wrapper = mountPanel()
    await wrapper.get('#review-score').setValue('90')
    await wrapper.get('#review-feedback').setValue('很好')
    await wrapper.get('.save-button').trigger('click')
    expect(wrapper.emitted('submit')[0][0]).toEqual({ score: 90, feedback: '很好' })
  })

  it('分数为空时提交 null', async () => {
    const wrapper = mountPanel()
    await wrapper.get('#review-score').setValue('')
    await wrapper.get('#review-feedback').setValue('仅反馈')
    await wrapper.get('.save-button').trigger('click')
    expect(wrapper.emitted('submit')[0][0]).toEqual({ score: null, feedback: '仅反馈' })
  })

  it('saving 时按钮禁用并显示保存中文案', () => {
    const wrapper = mountPanel({ saving: true })
    const button = wrapper.get('.save-button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.text()).toContain('保存中…')
  })

  it('展示上次保存时间', () => {
    const wrapper = mountPanel()
    expect(wrapper.text()).toContain('上次保存于')
  })
})
