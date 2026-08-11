const REQUIRED_LABELS = {
  title: '课程名称',
  description: '课程简介',
  academic_term_id: '所属学期',
  teaching_class_ids: '教学班',
  cover: '课程封面',
  start_time: '开课时间',
  visibility: '课程可见范围',
  default_score: '默认评分',
}

export function getCoursePublishMissingFields(course = {}) {
  const missing = []

  if (!String(course.title || '').trim()) missing.push(REQUIRED_LABELS.title)
  if (!String(course.description || '').trim()) missing.push(REQUIRED_LABELS.description)
  if (course.academic_term_id == null || course.academic_term_id === '') {
    missing.push(REQUIRED_LABELS.academic_term_id)
  }
  if (!Array.isArray(course.teaching_classes) || course.teaching_classes.length === 0) {
    if (!Array.isArray(course.teaching_class_ids) || course.teaching_class_ids.length === 0) {
      missing.push(REQUIRED_LABELS.teaching_class_ids)
    }
  }
  if (!String(course.cover || '').trim()) missing.push(REQUIRED_LABELS.cover)
  if (!String(course.start_time || '').trim()) missing.push(REQUIRED_LABELS.start_time)
  if (!String(course.visibility || '').trim()) missing.push(REQUIRED_LABELS.visibility)

  const defaultScore = Number(course.default_score)
  if (course.default_score == null || course.default_score === '' || !Number.isFinite(defaultScore)) {
    missing.push(REQUIRED_LABELS.default_score)
  }

  return missing
}

export function coursePublishMissingMessage(course = {}) {
  const missing = getCoursePublishMissingFields(course)
  return missing.length ? `发布前请完善：${missing.join('、')}` : ''
}
