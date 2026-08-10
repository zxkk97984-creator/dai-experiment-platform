export const ROLE_MAP = {
  student: { label: '学生', color: 'info' },
  teacher: { label: '教师', color: 'success' },
  admin: { label: '管理员', color: 'warning' },
  developer: { label: '开发者', color: 'info' },
}

export const USER_STATUS_MAP = {
  active: { label: '正常', color: 'success' },
  disabled: { label: '已禁用', color: 'danger' },
}

export const PUBLISH_STATUS_MAP = {
  draft: { label: '草稿', color: 'neutral' },
  published: { label: '已发布', color: 'success' },
  archived: { label: '已归档', color: 'warning' },
}

export const JUDGE_STATUS_MAP = {
  queued: { label: '排队中', color: 'info' },
  running: { label: '判题中', color: 'warning' },
  accepted: { label: '通过', color: 'success' },
  graded: { label: 'AI 评分完成', color: 'success' },
  wrong_answer: { label: '答案错误', color: 'danger' },
  runtime_error: { label: '运行错误', color: 'danger' },
  time_limit_exceeded: { label: '超时', color: 'warning' },
  system_error: { label: '系统错误', color: 'danger' },
}

export const EXAM_STATUS_MAP = {
  draft: { label: '草稿', color: 'neutral' },
  published: { label: '已发布', color: 'success' },
  ongoing: { label: '进行中', color: 'warning' },
  ended: { label: '已结束', color: 'neutral' },
  archived: { label: '已归档', color: 'neutral' },
}

export const ENROLL_STATUS_MAP = {
  enrolled: { label: '已选课', color: 'success' },
  dropped: { label: '已退课', color: 'neutral' },
}

export const EXPERIMENT_STATUS_MAP = {
  not_started: { label: '未开始', color: 'neutral', tone: 'pending' },
  started: { label: '进行中', color: 'info', tone: 'progress' },
  completed: { label: '已评分', color: 'success', tone: 'success' },
  submitted: { label: '已提交', color: 'warning', tone: 'submitted' },
  graded: { label: '已评分', color: 'success', tone: 'success' },
}

export function statusBadge(map, value) {
  const entry = map[value]
  if (!entry) return { label: value, color: 'neutral' }
  return entry
}
