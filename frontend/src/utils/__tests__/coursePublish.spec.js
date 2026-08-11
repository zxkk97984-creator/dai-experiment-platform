import { describe, expect, it } from 'vitest'

import { coursePublishMissingMessage, getCoursePublishMissingFields } from '../coursePublish.js'

const completeCourse = {
  title: 'Python 程序设计',
  description: '课程简介',
  academic_term_id: 1,
  teaching_classes: [{ id: 1 }],
  cover: 'covers/1/course.png',
  start_time: '2026-09-01T08:00',
  visibility: 'private',
  default_score: 100,
}

describe('coursePublish', () => {
  it('识别发布前缺失的基本信息', () => {
    const missing = getCoursePublishMissingFields({ title: '课程' })

    expect(missing).toEqual([
      '课程简介',
      '所属学期',
      '教学班',
      '课程封面',
      '开课时间',
      '课程可见范围',
      '默认评分',
    ])
    expect(coursePublishMissingMessage({ title: '课程' })).toContain('发布前请完善')
  })

  it('完整课程可以通过发布前校验', () => {
    expect(getCoursePublishMissingFields(completeCourse)).toEqual([])
    expect(coursePublishMissingMessage(completeCourse)).toBe('')
  })

  it('支持用教学班 ID 列表校验编辑表单', () => {
    const course = { ...completeCourse, teaching_class_ids: [1] }
    delete course.teaching_classes
    expect(getCoursePublishMissingFields({ ...course, teaching_class_ids: [1] })).toEqual([])
  })
})
