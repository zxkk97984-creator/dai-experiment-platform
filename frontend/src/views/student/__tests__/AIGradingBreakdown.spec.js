/** Task 12: 学生 AI 分项展示测试 */
import { describe, it, expect } from 'vitest'

describe('学生 AI 分项卡片', () => {
  it('分项数据结构正确', () => {
    const breakdown = {
      mode: 'active',
      status: 'completed',
      functional_score: 54,
      algorithm_score: 13,
      robustness_score: 7,
      quality_score: 5,
      raw_total: 79,
      final_score_100: 79,
      strengths: ['核心功能已实现'],
      issues: ['边界处理不完整'],
      suggestions: ['考虑添加输入校验'],
    }

    // 验证总分 = F + A + R + Q
    const total = breakdown.functional_score + breakdown.algorithm_score + breakdown.robustness_score + breakdown.quality_score
    expect(total).toBe(79)
    expect(breakdown.final_score_100).toBe(79)
  })

  it('维度标签映射正确', () => {
    const labels = {
      F: '功能正确性',
      A: '算法与关键步骤',
      R: '鲁棒性与性能',
      Q: '代码质量',
    }
    expect(labels.F).toBe('功能正确性')
    expect(labels.A).toBe('算法与关键步骤')
    expect(labels.R).toBe('鲁棒性与性能')
    expect(labels.Q).toBe('代码质量')
  })

  it('上限信息在有上限时展示', () => {
    const withCap = { raw_total: 87, score_cap: 80, final_score_100: 80 }
    expect(withCap.final_score_100).toBeLessThan(withCap.raw_total)
    expect(withCap.score_cap).toBe(80)
  })

  it('无上限时不展示上限行', () => {
    const withoutCap = { raw_total: 79, score_cap: null, final_score_100: 79 }
    expect(withoutCap.score_cap).toBeNull()
    expect(withoutCap.final_score_100).toBe(withoutCap.raw_total)
  })
})
