/** SubmissionReviewPanel 评分工作台组件契约测试：回填、提交载荷与 saving 状态 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SubmissionReviewPanel from '../SubmissionReviewPanel.vue'

function makeSubmission(overrides = {}) {
  return {
    id: 5,
    score: 85,
    feedback: '思路清晰，注意边界条件',
    reviewed_at: '2026-08-09T10:00:00Z',
    attempt_number: 2,
    submitted_at: '2026-08-09T09:30:00Z',
    cells_snapshot: {
      m1: '# 讲解',
      c1: 'print("x")',
      c2: 'print("y")',
    },
    cell_metadata: {
      m1: { type: 'markdown', order: 0 },
      c1: { type: 'code', order: 1 },
      c2: { type: 'code', order: 2 },
    },
    outputs_snapshot: {
      c1: { execution_count: 1, outputs: [{ output_type: 'stream', text: 'x\n' }] },
    },
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

  // ── 评分决策面板（执行证据 → 分数 → 反馈 → 发布评分）──

  it('展示发布评分按钮，且不包含评分流程条', () => {
    const wrapper = mountPanel({ submission: makeSubmission({ score: null, reviewed_at: null }) })
    const text = wrapper.text()
    expect(text).toContain('发布评分')
    expect(text).not.toContain('查看自动评估')
    expect(text).not.toContain('调整最终分数')
    expect(text).not.toContain('给出反馈')
    expect(text).not.toContain('自动评估')
    expect(wrapper.get('.save-button').text()).toContain('发布评分')
  })

  it('执行证据统计汇总', () => {
    const wrapper = mountPanel()
    const stats = wrapper.findAll('.stat')
    expect(stats).toHaveLength(4)
    expect(stats[0].text()).toContain('3') // 内容块
    expect(stats[1].text()).toContain('2') // 代码 Cell
    expect(stats[2].text()).toContain('1') // 已运行
    expect(stats[3].text()).toContain('0') // 执行异常
    expect(wrapper.text()).toContain('1 个 Cell 已运行')
    expect(wrapper.text()).toContain('第 2 次提交')
  })

  it('输出含异常时提示警告', () => {
    const wrapper = mountPanel({
      submission: makeSubmission({
        outputs_snapshot: {
          c1: { execution_count: 1, outputs: [{ output_type: 'error', ename: 'ZeroDivisionError', text: 'Traceback...' }] },
        },
      }),
    })
    expect(wrapper.findAll('.stat')[3].text()).toContain('1')
    expect(wrapper.text()).toContain('1 个 Cell 执行异常')
  })

  it('未运行任何 Cell 时给出人工评估提示', () => {
    const wrapper = mountPanel({
      submission: makeSubmission({ outputs_snapshot: {} }),
    })
    expect(wrapper.text()).toContain('学生提交时未运行任何 Cell')
  })

  it('快捷分数按钮填充输入并显示档位', async () => {
    const wrapper = mountPanel({ submission: makeSubmission({ score: null }) })
    expect(wrapper.text()).toContain('待评分')
    await wrapper.findAll('.score-chip').find((chip) => chip.text() === '90').trigger('click')
    expect(wrapper.get('#review-score').element.value).toBe('90')
    expect(wrapper.text()).toContain('优秀')
    expect(wrapper.text()).toContain('满分 100')
  })

  it('已评分提交展示已评分状态与上次分数', () => {
    const wrapper = mountPanel()
    expect(wrapper.text()).toContain('已评分')
    expect(wrapper.text()).toContain('上次评分：85 分')
  })
})
