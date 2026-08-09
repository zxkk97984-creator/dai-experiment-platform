// studentUi：学生视图纯函数模型。全部为纯函数——
// storage 与 now 由调用方注入，绝不读取全局 localStorage 或 Date.now；
// 任何缺失/损坏的日期、分数、存储数据都不会抛异常。

const DAY_MS = 24 * 60 * 60 * 1000

/** 解析日期为毫秒时间戳；缺失/非法返回 null（绝不抛异常） */
function parseDate(value) {
  if (value == null || value === '') return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d.getTime()
}

/** 当天零点（本地时区）时间戳 */
function startOfDay(ts) {
  const d = new Date(ts)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

/** 读取课程已完成课时 id 列表；存储损坏返回 [] */
function readCompleted(courseId, storage) {
  try {
    const raw = storage?.getItem?.(`course_${courseId}_completed`)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

/** 钳制 0–100，非法值视为 0 */
export function clampProgress(value) {
  const v = Number(value)
  if (Number.isNaN(v)) return 0
  return Math.round(Math.min(100, Math.max(0, v)))
}

/** 课程学习进度百分比（基于 localStorage 的已完成课时，与 CourseDetailView 同一 key） */
export function getCourseProgress(courseId, chapters, storage) {
  const completed = readCompleted(courseId, storage)
  let total = 0
  for (const ch of chapters || []) total += ch?.lessons?.length || 0
  if (total === 0) return 0
  // 只统计本课程实际存在的课时，避免其他课程 id 混入
  const done = completed.filter((id) =>
    (chapters || []).some((ch) => (ch?.lessons || []).some((l) => l?.id === id)),
  ).length
  return Math.round((done / total) * 100)
}

/** 第一个未完成课时；全部完成返回 null */
export function getFirstIncompleteLesson(courseId, chapters, storage) {
  const completed = new Set(readCompleted(courseId, storage))
  for (const ch of chapters || []) {
    for (const lesson of ch?.lessons || []) {
      if (lesson?.id != null && !completed.has(lesson.id)) return lesson
    }
  }
  return null
}

function courseTitleOf(courseMap, courseId) {
  return courseMap?.[courseId]?.title ?? ''
}

/** 作业 → 任务视图模型 */
export function normalizeAssignmentTask(item, courseMap, now) {
  const id = item?.id ?? null
  return {
    kind: 'assignment',
    id,
    title: item?.title ?? '',
    courseId: item?.course_id ?? null,
    courseTitle: courseTitleOf(courseMap, item?.course_id),
    dueAt: parseDate(item?.due_at),
    submitted: !!item?.is_submitted,
    route: id == null ? null : `/student/assignments/${id}`,
  }
}

/** 考试 → 任务视图模型（以结束时间为截止） */
export function normalizeExamTask(item, courseMap, now) {
  const id = item?.id ?? null
  return {
    kind: 'exam',
    id,
    title: item?.title ?? '',
    courseId: item?.course_id ?? null,
    courseTitle: courseTitleOf(courseMap, item?.course_id),
    dueAt: parseDate(item?.ends_at ?? item?.starts_at),
    submitted: !!item?.is_submitted,
    status: item?.status ?? null,
    route: id == null ? null : `/student/exams/${id}`,
  }
}

/** 实验记录 → 任务视图模型（无截止日期，路由指向实验页面） */
export function normalizeExperimentTask(item, courseMap, now) {
  const id = item?.id ?? null
  const targetId = item?.lesson_id ?? item?.module_id ?? id
  return {
    kind: 'experiment',
    id,
    title: item?.title ?? '',
    courseId: item?.course_id ?? null,
    courseTitle: courseTitleOf(courseMap, item?.course_id),
    dueAt: null,
    status: item?.status ?? null,
    route: targetId == null ? null : `/student/experiments/${targetId}`,
  }
}

/**
 * 任务状态：已提交优先，其次逾期（截止在过去），其余为待办。
 * now 未注入时不做逾期判断。
 */
export function taskStatus(item, now) {
  if (!item) return 'pending'
  // 作业：submitted 布尔（后端 is_submitted）；考试/实验：状态机值（实验 started/submitted/graded）
  if (item.submitted || item.status === 'submitted' || item.status === 'accepted' || item.status === 'graded') return 'submitted'
  if (item.dueAt != null && now != null) {
    const due = new Date(item.dueAt).getTime()
    const t = new Date(now).getTime()
    if (Number.isNaN(due) || Number.isNaN(t)) return 'pending'
    if (due < t) return 'overdue'
  }
  return 'pending'
}

/**
 * 按截止时间分组：overdue / today / tomorrow / this_week / later / no_deadline。
 * 不发明日期——缺失或损坏的截止归 no_deadline。
 */
export function groupTasksByDeadline(items, now) {
  const groups = { overdue: [], today: [], tomorrow: [], this_week: [], later: [], no_deadline: [] }
  // 未注入 now 时无法判断时间归属，全部归 no_deadline，不做臆测
  if (now == null) {
    for (const item of items || []) groups.no_deadline.push(item)
    return groups
  }
  const t = new Date(now).getTime()
  const todayStart = startOfDay(t)
  // 本周日零点（getDay()：0=周日 … 6=周六）
  const sundayStart = todayStart + DAY_MS * ((7 - new Date(todayStart).getDay()) % 7)
  for (const item of items || []) {
    const due = parseDate(item?.dueAt)
    if (due == null) { groups.no_deadline.push(item); continue }
    if (due < todayStart) groups.overdue.push(item)
    else if (due < todayStart + DAY_MS) groups.today.push(item)
    else if (due < todayStart + 2 * DAY_MS) groups.tomorrow.push(item)
    // 本周包含周日整天（到次日零点前）
    else if (sundayStart > todayStart && due < sundayStart + DAY_MS) groups.this_week.push(item)
    else groups.later.push(item)
  }
  return groups
}

/** 反馈状态：无分数等待评分；<60 需修改；≥60 通过 */
export function feedbackStatus(item) {
  const score = item?.score
  if (score == null || score === '') return 'pending'
  const s = Number(score)
  if (Number.isNaN(s)) return 'pending'
  return s < 60 ? 'needs_revision' : 'passed'
}

/** 反馈组合过滤：状态 / 课程 / 关键字（标题与课程名） */
export function filterFeedback(items, filters) {
  const f = filters || {}
  const query = (f.query || '').trim().toLowerCase()
  return (items || []).filter((item) => {
    if (f.status && f.status !== 'all' && feedbackStatus(item) !== f.status) return false
    if (f.courseId != null && f.courseId !== '') {
      // 优先按 courseId 数字比较；数据源无 courseId 时按 courseTitle 兜底（如 dashboard 聚合）
      const own = item?.courseId ?? item?.course_title
      if (own == null || String(own) !== String(f.courseId)) return false
    }
    if (query) {
      const hay = `${item?.title || ''} ${item?.courseTitle || ''}`.toLowerCase()
      if (!hay.includes(query)) return false
    }
    return true
  })
}
