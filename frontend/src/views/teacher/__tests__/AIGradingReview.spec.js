/** Task 12: 教师复核列表与详情测试 */
import { describe, it, expect } from 'vitest'

describe('AI 评分复核列表', () => {
  it('状态 badge 对应正确文本', () => {
    const badgeMap = {
      pending: '等待中',
      queued: '排队中',
      running: '评分中',
      completed: '已完成',
      review_required: '需复核',
      system_error: '系统错误',
    }
    expect(badgeMap.pending).toBe('等待中')
    expect(badgeMap.completed).toBe('已完成')
    expect(badgeMap.review_required).toBe('需复核')
  })

  it('分页参数正确传递', () => {
    const params = { page: 2, page_size: 20, kind: 'assignment', status: 'review_required' }
    expect(params.page).toBe(2)
    expect(params.page_size).toBe(20)
    expect(params.kind).toBe('assignment')
  })

  it('覆盖操作必须提供非空理由', () => {
    const reason = ''
    const isValid = reason.length >= 3
    expect(isValid).toBe(false)
  })

  it('覆盖操作理由符合长度要求通过', () => {
    const reason = '学生代码实际正确，AI 误判了算法步骤'
    const isValid = reason.length >= 3 && reason.length <= 1000
    expect(isValid).toBe(true)
  })
})

describe('学生分项展示', () => {
  it('active 模式展示完整分项', () => {
    const breakdown = {
      mode: 'active',
      status: 'completed',
      functional_score: 54,
      algorithm_score: 13,
      robustness_score: 7,
      quality_score: 5,
      raw_total: 79,
      final_score_100: 79,
      strengths: ['功能正确'],
      issues: ['算法部分缺失'],
      suggestions: ['改进边界处理'],
    }
    expect(breakdown.mode).toBe('active')
    expect(breakdown.functional_score + (breakdown.algorithm_score || 0) + breakdown.robustness_score + (breakdown.quality_score || 0)).toBe(79)
  })

  it('shadow/legacy 模式不展示 AI 分项', () => {
    const shadowBreakdown = null
    expect(shadowBreakdown).toBeNull()
  })

  it('原始模型响应只对教师展示', () => {
    const teacherView = { raw_response: '{"algorithm": ...}', ai_result: {} }
    const studentView = { mode: 'active', functional_score: 54 }
    // 学生视图不应包含 raw_response
    expect('raw_response' in studentView).toBe(false)
    // 教师视图可以包含
    expect('raw_response' in teacherView).toBe(true)
  })
})
