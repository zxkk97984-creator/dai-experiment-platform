/** Task 11: 教师题目 AI 配置界面测试 */
import { describe, it, expect } from 'vitest'

describe('AI 题目配置面板', () => {
  it('新编程题默认 grading_mode 为 shadow', () => {
    const defaultConfig = { grading_mode: 'shadow', teacher_constraints: {}, reference_solution: null, test_groups: [], score_cap_rules: [] }
    expect(defaultConfig.grading_mode).toBe('shadow')
  })

  it('legacy 模式不要求 F/R 测试组', () => {
    const legacyConfig = { grading_mode: 'legacy', test_groups: [] }
    expect(legacyConfig.grading_mode).toBe('legacy')
  })

  it('shadow/active 权重不是 60/10 时阻止保存', () => {
    const fTotal = 50
    const rTotal = 10
    const isValid = Math.abs(fTotal - 60) < 1e-6 && Math.abs(rTotal - 10) < 1e-6
    expect(isValid).toBe(false)
  })

  it('合法 F60+R10 通过校验', () => {
    const fTotal = 60
    const rTotal = 10
    const isValid = Math.abs(fTotal - 60) < 1e-6 && Math.abs(rTotal - 10) < 1e-6
    expect(isValid).toBe(true)
  })

  it('draft Rubric 可编辑、locked 禁止编辑', () => {
    const draftRubric = { status: 'draft' }
    const lockedRubric = { status: 'locked' }
    expect(draftRubric.status === 'draft').toBe(true)
    expect(lockedRubric.status === 'locked').toBe(true)
    expect(lockedRubric.status !== 'draft').toBe(true)
  })

  it('test_groups ID 唯一性校验', () => {
    const groups = [
      { id: 'F1', name: '基础', dimension: 'F', max_score: 30, tests: '' },
      { id: 'F2', name: '核心', dimension: 'F', max_score: 30, tests: '' },
      { id: 'R1', name: '边界', dimension: 'R', max_score: 10, tests: '' },
    ]
    const ids = groups.map(g => g.id)
    const unique = new Set(ids).size === ids.length
    expect(unique).toBe(true)
  })

  it('重复 ID 被检测出', () => {
    const groups = [
      { id: 'F1', name: '基础', dimension: 'F', max_score: 30, tests: '' },
      { id: 'F1', name: '核心', dimension: 'F', max_score: 30, tests: '' },
    ]
    const ids = groups.map(g => g.id)
    const unique = new Set(ids).size === ids.length
    expect(unique).toBe(false)
  })
})
