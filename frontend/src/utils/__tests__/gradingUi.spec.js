// gradingUi：教师评分详情视图纯函数模型测试。
// 覆盖中文化文本、六态状态推导、总分预览（含 cap=0 与字符串数字）、
// 测试摘要聚合、反馈自然文案与坏数据容错。

import { describe, it, expect } from 'vitest'
import {
  modeText, statusText, reviewState, dimensionRows, safeNumber,
  autoTotal, testSummary, feedbackBlocks, fmtDateTime,
} from '../gradingUi.js'

describe('modeText / statusText 中文化', () => {
  it('模式文本', () => {
    expect(modeText('active')).toBe('自动评分')
    expect(modeText('shadow')).toBe('影子评分')
    expect(modeText('legacy')).toBe('传统评分')
    expect(modeText('unknown')).toBe('')
    expect(modeText(null)).toBe('')
  })

  it('状态文本', () => {
    expect(statusText('pending')).toBe('等待中')
    expect(statusText('queued')).toBe('排队中')
    expect(statusText('running')).toBe('评分中')
    expect(statusText('completed')).toBe('已完成')
    expect(statusText('review_required')).toBe('需复核')
    expect(statusText('system_error')).toBe('系统错误')
    expect(statusText('nope')).toBe('')
  })
})

describe('reviewState 六态推导', () => {
  it('进行中：无主操作', () => {
    expect(reviewState({ status: 'pending' }).label).toBe('AI 正在评分')
    expect(reviewState({ status: 'queued' }).label).toBe('AI 正在评分')
    expect(reviewState({ status: 'running' }).label).toBe('AI 正在评分')
  })

  it('review_required：等待教师复核', () => {
    const s = reviewState({ status: 'review_required', needs_teacher_review: true })
    expect(s.label).toBe('等待教师复核')
    expect(s.tone).toBe('warning')
    expect(s.key).toBe('review')
  })

  it('completed + active + 无 override：已生效', () => {
    const s = reviewState({ status: 'completed', mode: 'active', overrides: [] })
    expect(s.label).toBe('AI 评分已生效')
    expect(s.tone).toBe('success')
  })

  it('completed + 有 override：教师已调整', () => {
    const s = reviewState({ status: 'completed', mode: 'active', overrides: [{}] })
    expect(s.label).toBe('教师已调整并生效')
  })

  it('completed + shadow：影子评分', () => {
    const s = reviewState({ status: 'completed', mode: 'shadow', overrides: [] })
    expect(s.label).toBe('影子评分，不影响正式成绩')
    expect(s.tone).toBe('neutral')
  })

  it('system_error：评分失败', () => {
    const s = reviewState({ status: 'system_error' })
    expect(s.label).toBe('评分失败')
    expect(s.tone).toBe('danger')
  })

  it('未知状态不抛异常', () => {
    const s = reviewState({ status: 'weird' })
    expect(s.label).toBe('')
    expect(reviewState(null).label).toBe('')
  })
})

describe('dimensionRows 四条中文维度', () => {
  const detail = {
    functional_score: 54, algorithm_score: 13,
    robustness_score: 7, quality_score: 5,
  }

  it('生成 F/A/R/Q 四条', () => {
    const rows = dimensionRows(detail)
    expect(rows).toHaveLength(4)
    expect(rows[0]).toMatchObject({ key: 'functional', label: '功能正确性', letter: 'F', score: 54, max: 60 })
    expect(rows[1]).toMatchObject({ key: 'algorithm', label: '算法关键步骤', letter: 'A', score: 13, max: 20 })
    expect(rows[2]).toMatchObject({ key: 'robustness', label: '鲁棒性与性能', letter: 'R', score: 7, max: 10 })
    expect(rows[3]).toMatchObject({ key: 'quality', label: '代码质量', letter: 'Q', score: 5, max: 10 })
  })

  it('A/Q 缺失时为 null，不强制 0', () => {
    const rows = dimensionRows({ functional_score: 60, robustness_score: 10 })
    expect(rows[1].score).toBeNull()
    expect(rows[3].score).toBeNull()
    expect(rows[0].score).toBe(60)
  })

  it('字符串数字安全转换', () => {
    const rows = dimensionRows({ functional_score: '54', robustness_score: 10 })
    expect(rows[0].score).toBe(54)
  })
})

describe('safeNumber', () => {
  it('数字/字符串/坏值', () => {
    expect(safeNumber(5)).toBe(5)
    expect(safeNumber('60')).toBe(60)
    expect(safeNumber('abc')).toBe(0)
    expect(safeNumber(NaN)).toBe(0)
    expect(safeNumber(Infinity)).toBe(0)
    expect(safeNumber(null)).toBe(0)
    expect(safeNumber(undefined)).toBe(0)
  })
})

describe('autoTotal 总分预览', () => {
  const detail = { functional_score: 60, robustness_score: 10, algorithm_score: 15, quality_score: 8 }

  it('维度合并：F+R+A+Q', () => {
    expect(autoTotal(detail, {})).toEqual({ raw: 93, final: 93 })
    // 非直接调整模式不标记 direct
    expect(autoTotal(detail, {})).not.toHaveProperty('direct')
  })

  it('修改 A/Q 后重算', () => {
    expect(autoTotal(detail, { a: 10, q: 5 }).raw).toBe(85)
  })

  it('cap 存在时截断', () => {
    expect(autoTotal(detail, {}).final).toBe(93)
    expect(autoTotal({ ...detail, score_cap: 90 }, {}).final).toBe(90)
  })

  it('cap=0 是合法上限，不能用 truthy 判断', () => {
    expect(autoTotal({ ...detail, score_cap: 0 }, {}).final).toBe(0)
  })

  it('score_cap 为 null 时无上限（Number(null)=0 的坑）', () => {
    expect(autoTotal({ ...detail, score_cap: null }, {}).final).toBe(93)
  })

  it('直接调整总分模式', () => {
    const r = autoTotal(detail, { useFinal: true, final: 88 })
    expect(r).toEqual({ raw: 88, final: 88, direct: true })
  })

  it('字符串数字安全', () => {
    expect(autoTotal({ functional_score: '60', robustness_score: '10', algorithm_score: 15, quality_score: 8 }, {}).raw).toBe(93)
  })

  it('空详情不抛异常', () => {
    expect(autoTotal(null, {}).raw).toBe(0)
  })
})

describe('testSummary 测试摘要', () => {
  it('聚合各组的通过/失败/错误', () => {
    const groups = [
      { counts: { passed: 8, failed: 1, errors: 0 } },
      { counts: { passed: 4, failed: 2, errors: 1 } },
    ]
    expect(testSummary(groups)).toEqual({ passed: 12, failed: 3, errors: 1, total: 16 })
  })

  it('字符串计数安全转换（避免 "60"+20 拼接）', () => {
    const groups = [{ counts: { passed: '60', failed: '1', errors: 0 } }]
    expect(testSummary(groups)).toEqual({ passed: 60, failed: 1, errors: 0, total: 61 })
  })

  it('缺失计数与空组', () => {
    expect(testSummary([])).toEqual({ passed: 0, failed: 0, errors: 0, total: 0 })
    expect(testSummary([{ counts: {} }]).total).toBe(0)
    expect(testSummary(null).total).toBe(0)
  })
})

describe('feedbackBlocks 学生反馈区块', () => {
  it('有内容时原样展示', () => {
    const blocks = feedbackBlocks({ strengths: ['a'], issues: ['b'], suggestions: ['c'] })
    expect(blocks[0]).toMatchObject({ key: 'strengths', title: '做得较好的部分', items: ['a'] })
    expect(blocks[1]).toMatchObject({ key: 'issues', title: '需要改进', items: ['b'] })
    expect(blocks[2]).toMatchObject({ key: 'suggestions', title: '后续建议', items: ['c'] })
  })

  it('空数组给出自然文案，不机械显示"无"', () => {
    const blocks = feedbackBlocks({ strengths: [], issues: [], suggestions: [] })
    expect(blocks[1].emptyText).toContain('未发现需要修改')
    expect(blocks[2].emptyText.length).toBeGreaterThan(4)
  })

  it('缺失反馈对象不抛异常', () => {
    expect(feedbackBlocks(null)).toHaveLength(3)
    expect(feedbackBlocks(undefined)[0].items).toEqual([])
  })
})

describe('fmtDateTime', () => {
  it('正常时间格式化为 zh-CN（数字月日 + 时分）', () => {
    const out = fmtDateTime('2026-08-02T11:32:00')
    expect(out).toContain('8/2')
    expect(out).toContain('11:32')
  })

  it('坏数据返回空串', () => {
    expect(fmtDateTime(null)).toBe('')
    expect(fmtDateTime('')).toBe('')
    expect(fmtDateTime('not-a-date')).toBe('')
  })
})
