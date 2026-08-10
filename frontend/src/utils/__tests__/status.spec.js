/** 状态映射测试：考试评分状态键完整性、未知值回退 */
import { describe, it, expect } from 'vitest'
import { EXAM_GRADE_STATUS_MAP, EXAM_STATUS_MAP, statusBadge } from '../status.js'

describe('EXAM_GRADE_STATUS_MAP', () => {
  it('覆盖全部考试评分状态且文案正确', () => {
    expect(EXAM_GRADE_STATUS_MAP.graded).toEqual({ label: '已评分', color: 'success' })
    expect(EXAM_GRADE_STATUS_MAP.review_required).toEqual({ label: '待复核', color: 'warning' })
    expect(EXAM_GRADE_STATUS_MAP.grading).toEqual({ label: '评分中', color: 'info' })
    expect(EXAM_GRADE_STATUS_MAP.submitted).toEqual({ label: '已交卷', color: 'info' })
    expect(EXAM_GRADE_STATUS_MAP.started).toEqual({ label: '进行中', color: 'info' })
    expect(EXAM_GRADE_STATUS_MAP.absent).toEqual({ label: '缺考', color: 'danger' })
  })
})

describe('statusBadge', () => {
  it('已知状态返回映射条目', () => {
    expect(statusBadge(EXAM_STATUS_MAP, 'draft').label).toBe('草稿')
    expect(statusBadge(EXAM_GRADE_STATUS_MAP, 'graded').label).toBe('已评分')
  })

  it('未知值回退为原值与中性色', () => {
    expect(statusBadge(EXAM_GRADE_STATUS_MAP, 'unknown_status')).toEqual({ label: 'unknown_status', color: 'neutral' })
  })
})
