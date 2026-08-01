import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StudentAIGradingResult from '../StudentAIGradingResult.vue'

const breakdown = {
  functional_score: 54,
  algorithm_score: 13,
  robustness_score: 7,
  quality_score: 5,
  raw_total: 79,
  score_cap: null,
  final_score_100: 79,
  strengths: ['核心功能已实现'],
  issues: ['边界处理不完整'],
  suggestions: ['考虑添加输入校验'],
  code_suggestions: [
    {
      title: '补全空输入处理',
      diff: '--- a/solution.py\n+++ b/solution.py\n@@ -1,6 +1,8 @@\n def solve(nums):\n+    if not nums:\n+        return []\n',
    },
  ],
  algorithm_items: [
    {
      criterion_id: 'A1',
      criterion: '维护有效搜索区间',
      level: 'partial',
      score: 3,
      max_score: 4,
      code_lines: [2, 5],
      evidence: '边界条件未覆盖空数组',
      deduction_reason: '缺少空输入判断',
    },
  ],
  quality_items: [],
  test_groups: [
    {
      id: 'F1',
      name: '功能正确性',
      max_score: 60,
      score: 54,
      counts: { passed: 3, failed: 1, errors: 0, skipped: 0 },
    },
  ],
}

describe('StudentAIGradingResult', () => {
  it('以最终得分为焦点并展示四个维度进度', () => {
    const wrapper = mount(StudentAIGradingResult, {
      props: { breakdown },
    })
    const text = wrapper.text()
    expect(text).toContain('AI 评分详情')
    expect(text).toContain('最终得分')
    expect(text).toContain('79')
    expect(text).toContain('功能正确性 F')
    expect(text).toContain('54 / 60')
    expect(text).toContain('算法关键步骤 A')
    expect(text).toContain('13 / 20')
  })

  it('展示问题、建议与代码 diff', () => {
    const wrapper = mount(StudentAIGradingResult, {
      props: { breakdown },
    })
    const text = wrapper.text()
    expect(text).toContain('问题')
    expect(text).toContain('边界处理不完整')
    expect(text).toContain('改进建议')
    expect(text).toContain('补全空输入处理')
    expect(text).toContain('+        return []')
  })

  it('提供可折叠扣分依据和测试用例结果', async () => {
    const wrapper = mount(StudentAIGradingResult, {
      props: { breakdown },
    })
    expect(wrapper.text()).toContain('扣分依据')
    expect(wrapper.text()).toContain('维护有效搜索区间')
    expect(wrapper.text()).toContain('缺少空输入判断')
    expect(wrapper.text()).toContain('测试用例结果')
    expect(wrapper.text()).toContain('通过 3')
    expect(wrapper.text()).toContain('失败 1')
  })

  it('不使用渐变、玻璃拟态或发光装饰', () => {
    const wrapper = mount(StudentAIGradingResult, {
      props: { breakdown },
    })
    const html = wrapper.html()
    expect(html).not.toContain('linear-gradient')
    expect(html).not.toContain('backdrop-filter')
    expect(html).not.toContain('box-shadow')
  })
})
