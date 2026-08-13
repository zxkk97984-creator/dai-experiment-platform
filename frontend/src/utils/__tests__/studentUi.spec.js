// studentUi 纯函数视图模型：注入 storage/now，坏数据不抛异常
import { describe, expect, it } from 'vitest'
import {
  clampProgress,
  feedbackStatus,
  filterFeedback,
  groupTasksByDeadline,
  normalizeAssignmentTask,
  normalizeExamTask,
  normalizeExperimentTask,
  taskStatus,
} from '../studentUi.js'

// 本地时区 2026-07-30（周四）12:00 —— 本周日 8-02，可覆盖全部截止桶
const NOW = new Date(2026, 6, 30, 12, 0, 0)
const iso = (y, m, d, h = 0) => new Date(y, m, d, h).toISOString()

describe('clampProgress', () => {
  it('低于 0 钳制到 0，高于 100 钳制到 100', () => {
    expect(clampProgress(-5)).toBe(0)
    expect(clampProgress(150)).toBe(100)
  })
  it('非法值视为 0', () => {
    expect(clampProgress(null)).toBe(0)
    expect(clampProgress('abc')).toBe(0)
    expect(clampProgress(undefined)).toBe(0)
  })
  it('数字字符串可解析', () => {
    expect(clampProgress('42')).toBe(42)
  })
})

const COURSES = { 5: { id: 5, title: 'Python 入门' } }

describe('normalizeAssignmentTask', () => {
  it('映射标题、课程、截止时间并生成学生路由', () => {
    const t = normalizeAssignmentTask(
      { id: 7, title: '作业一', course_id: 5, due_at: iso(2026, 6, 31), is_submitted: false },
      COURSES,
      NOW,
    )
    expect(t.kind).toBe('assignment')
    expect(t.title).toBe('作业一')
    expect(t.courseTitle).toBe('Python 入门')
    expect(t.dueAt).toBe(new Date(iso(2026, 6, 31)).getTime())
    expect(t.route).toBe('/student/assignments/7')
  })
  it('缺失字段与坏日期不抛异常', () => {
    const t = normalizeAssignmentTask({ due_at: 'not-a-date' }, COURSES, NOW)
    expect(t.dueAt).toBeNull()
    expect(t.title).toBe('')
  })
  it('is_submitted 映射到 submitted 且 taskStatus 返回 submitted（任务中心已交作业）', () => {
    const t = normalizeAssignmentTask(
      { id: 7, title: '作业一', course_id: 5, due_at: iso(2026, 6, 31), is_submitted: true },
      COURSES,
      NOW,
    )
    expect(t.submitted).toBe(true)
    expect(taskStatus(t, NOW)).toBe('submitted')
  })
  it('缺少 id 时路由保持为空而非非法链接', () => {
    const t = normalizeAssignmentTask({ title: 'x' }, COURSES, NOW)
    expect(t.route).toBeNull()
  })
  it('归一化路由保持在 /student 下', () => {
    const t = normalizeAssignmentTask({ id: 1 }, COURSES, NOW)
    expect(t.route.startsWith('/student/')).toBe(true)
  })
})

describe('normalizeExamTask', () => {
  it('以结束时间为截止并生成考试路由', () => {
    const t = normalizeExamTask(
      { id: 3, title: '期中考试', course_id: 5, ends_at: iso(2026, 7, 2), status: 'published' },
      COURSES,
      NOW,
    )
    expect(t.kind).toBe('exam')
    expect(t.dueAt).toBe(new Date(iso(2026, 7, 2)).getTime())
    expect(t.route).toBe('/student/exams/3')
    expect(t.courseTitle).toBe('Python 入门')
  })
  it('缺失 ends_at 不抛异常且无截止', () => {
    const t = normalizeExamTask({ id: 3, title: 'x' }, COURSES, NOW)
    expect(t.dueAt).toBeNull()
  })
})

describe('normalizeExperimentTask', () => {
  it('实验无截止日期但保留真实 id 路由', () => {
    const t = normalizeExperimentTask(
      { id: 9, lesson_id: 12, title: '实验记录', status: 'started' },
      COURSES,
      NOW,
    )
    expect(t.kind).toBe('experiment')
    expect(t.dueAt).toBeNull()
    expect(t.route).toBe('/student/experiments/12')
  })
})

describe('taskStatus', () => {
  it('已提交优先返回 submitted', () => {
    expect(taskStatus({ submitted: true, dueAt: new Date(NOW).getTime() - 1000 }, NOW)).toBe('submitted')
  })
  it('截止已过时逾期优先于待办', () => {
    expect(taskStatus({ submitted: false, dueAt: new Date(NOW).getTime() - 1000 }, NOW)).toBe('overdue')
  })
  it('未来截止为 pending', () => {
    expect(taskStatus({ submitted: false, dueAt: new Date(NOW).getTime() + 1000 }, NOW)).toBe('pending')
  })
  it('坏日期或缺失日期不抛异常且视为 pending', () => {
    expect(taskStatus({ submitted: false, dueAt: null }, NOW)).toBe('pending')
    expect(taskStatus({ submitted: false, dueAt: 'junk' }, NOW)).toBe('pending')
  })
  it('实验记录 submitted/graded 均视为已提交', () => {
    expect(taskStatus({ status: 'submitted', dueAt: null }, NOW)).toBe('submitted')
    expect(taskStatus({ status: 'graded', dueAt: null }, NOW)).toBe('submitted')
  })
})

describe('groupTasksByDeadline', () => {
  const mk = (dueAt) => ({ id: String(dueAt), dueAt })
  it('按逾期/今天/明天/本周/更晚分组', () => {
    const items = [
      mk(new Date(iso(2026, 6, 29)).getTime()), // overdue
      mk(new Date(iso(2026, 6, 30)).getTime()), // today
      mk(new Date(iso(2026, 6, 31)).getTime()), // tomorrow
      mk(new Date(iso(2026, 7, 1)).getTime()),  // this week (8-01)
      mk(new Date(iso(2026, 7, 2)).getTime()),  // this week (8-02 周日)
      mk(new Date(iso(2026, 7, 3)).getTime()),  // later
      mk(null),                                 // no deadline
    ]
    const groups = groupTasksByDeadline(items, NOW)
    expect(groups.overdue.length).toBe(1)
    expect(groups.today.length).toBe(1)
    expect(groups.tomorrow.length).toBe(1)
    expect(groups.this_week.length).toBe(2)
    expect(groups.later.length).toBe(1)
    expect(groups.no_deadline.length).toBe(1)
  })
  it('坏日期归入 no_deadline', () => {
    const groups = groupTasksByDeadline([{ id: 1, dueAt: 'junk' }], NOW)
    expect(groups.no_deadline.length).toBe(1)
  })
  it('未提供 now 时全部归入 no_deadline（不做时间臆测）', () => {
    const groups = groupTasksByDeadline([mk(new Date(iso(2026, 6, 29)).getTime())], null)
    expect(groups.no_deadline.length).toBe(1)
  })
})

describe('feedbackStatus', () => {
  it('分数低于 60 为需修改，60 及以上为通过', () => {
    expect(feedbackStatus({ score: 59 })).toBe('needs_revision')
    expect(feedbackStatus({ score: 60 })).toBe('passed')
    expect(feedbackStatus({ score: 100 })).toBe('passed')
  })
  it('无分数为等待评分', () => {
    expect(feedbackStatus({ score: null })).toBe('pending')
    expect(feedbackStatus({})).toBe('pending')
  })
  it('坏分数不抛异常且视为等待评分', () => {
    expect(feedbackStatus({ score: 'abc' })).toBe('pending')
  })
})

describe('filterFeedback', () => {
  const items = [
    { id: 1, title: '作业一', courseId: 5, courseTitle: 'Python 入门', score: 85 },
    { id: 2, title: '作业二', courseId: 6, courseTitle: '数据结构', score: 45 },
    { id: 3, title: '作业三', courseId: 5, courseTitle: 'Python 入门', score: null },
  ]
  it('状态过滤', () => {
    expect(filterFeedback(items, { status: 'passed' }).map((i) => i.id)).toEqual([1])
    expect(filterFeedback(items, { status: 'needs_revision' }).map((i) => i.id)).toEqual([2])
    expect(filterFeedback(items, { status: 'pending' }).map((i) => i.id)).toEqual([3])
    expect(filterFeedback(items, { status: 'all' }).length).toBe(3)
  })
  it('课程与搜索组合过滤', () => {
    expect(filterFeedback(items, { courseId: 5, query: '作业一' }).map((i) => i.id)).toEqual([1])
    expect(filterFeedback(items, { courseId: 5 }).length).toBe(2)
    expect(filterFeedback(items, { query: '数据' }).map((i) => i.id)).toEqual([2])
  })
  it('空过滤条件返回全部', () => {
    expect(filterFeedback(items, {}).length).toBe(3)
  })
})
