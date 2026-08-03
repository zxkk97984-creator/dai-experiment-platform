// gradingUi：教师评分详情视图纯函数模型。
// 全部为纯函数，任何缺失/损坏的字段都不抛异常；
// 数字一律经 safeNumber 转换，避免字符串拼接（"60"+20）与 cap=0 误判。

/** 数字安全转换：非有限值归 0 */
export function safeNumber(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

/** 评分模式中文化 */
export function modeText(mode) {
  const map = { active: '自动评分', shadow: '影子评分', legacy: '传统评分' }
  return map[mode] || ''
}

/** 评分状态中文化 */
export function statusText(status) {
  const map = {
    pending: '等待中', queued: '排队中', running: '评分中',
    completed: '已完成', review_required: '需复核', system_error: '系统错误',
  }
  return map[status] || ''
}

/**
 * 页面状态推导（六态，不虚构后端不存在的状态）：
 * - pending/queued/running：AI 正在评分
 * - review_required：等待教师复核（warning）
 * - completed + active + 无 override：AI 评分已生效
 * - completed + 有 override：教师已调整并生效
 * - completed + shadow：影子评分，不影响正式成绩
 * - system_error：评分失败
 */
export function reviewState(detail) {
  const d = detail || {}
  const status = d.status
  if (status === 'pending' || status === 'queued' || status === 'running') {
    return { key: 'running', label: 'AI 正在评分', tone: 'progress' }
  }
  if (status === 'review_required') {
    return { key: 'review', label: '等待教师复核', tone: 'warning' }
  }
  if (status === 'completed') {
    if (Array.isArray(d.overrides) && d.overrides.length > 0) {
      return { key: 'adjusted', label: '教师已调整并生效', tone: 'success' }
    }
    if (d.mode === 'shadow') {
      return { key: 'shadow', label: '影子评分，不影响正式成绩', tone: 'neutral' }
    }
    if (d.mode === 'active') {
      return { key: 'effective', label: 'AI 评分已生效', tone: 'success' }
    }
    return { key: 'completed', label: 'AI 评分已完成', tone: 'success' }
  }
  if (status === 'system_error') {
    return { key: 'system_error', label: '评分失败', tone: 'danger' }
  }
  return { key: 'unknown', label: statusText(status), tone: 'neutral' }
}

/** F/A/R/Q 四条中文评分维度；A/Q 未评分时为 null（不强制 0） */
export function dimensionRows(detail) {
  const d = detail || {}
  const row = (key, label, letter, max, score) => ({
    key, label, letter, max,
    score: score == null ? null : safeNumber(score),
  })
  return [
    row('functional', '功能正确性', 'F', 60, d.functional_score),
    row('algorithm', '算法关键步骤', 'A', 20, d.algorithm_score),
    row('robustness', '鲁棒性与性能', 'R', 10, d.robustness_score),
    row('quality', '代码质量', 'Q', 10, d.quality_score),
  ]
}

function applyCap(raw, detail) {
  const cap = detail?.score_cap
  // null/undefined 无上限；cap 可能为 0（合法上限），用 isFinite 而非 truthy。
  // 注意 Number(null)=0，必须先判空再转换。
  if (cap == null) return raw
  const n = Number(cap)
  return Number.isFinite(n) ? Math.min(raw, n) : raw
}

/**
 * 总分预览：默认 F+R+A+Q 合并；useFinal 时直接取总分输入。
 * 返回 { raw, final, direct }，提交后以后端合分为准。
 */
export function autoTotal(detail, opts = {}) {
  const d = detail || {}
  if (opts.useFinal) {
    const f = safeNumber(opts.final)
    return { raw: f, final: applyCap(f, d), direct: true }
  }
  const a = opts.a == null ? safeNumber(d.algorithm_score) : safeNumber(opts.a)
  const q = opts.q == null ? safeNumber(d.quality_score) : safeNumber(opts.q)
  const raw = safeNumber(d.functional_score) + safeNumber(d.robustness_score) + a + q
  return { raw, final: applyCap(raw, d) }
}

/**
 * 测试摘要：聚合各组的通过/失败/错误计数。
 * total = passed + failed + errors；系统错误列表不重复计入测试点总数。
 */
export function testSummary(groups) {
  let passed = 0
  let failed = 0
  let errors = 0
  for (const g of groups || []) {
    const c = g?.counts || {}
    passed += safeNumber(c.passed)
    failed += safeNumber(c.failed)
    errors += safeNumber(c.errors)
  }
  return { passed, failed, errors, total: passed + failed + errors }
}

const EMPTY_TEXT = {
  strengths: '本次提交没有特别突出的亮点。',
  issues: '本次提交未发现需要修改的核心问题。',
  suggestions: '可以保持当前的实现方式，无需额外调整。',
}

/** 学生反馈三区块；空数组给出自然文案，不机械显示"无" */
export function feedbackBlocks(feedback) {
  const src = feedback || {}
  return [
    { key: 'strengths', title: '做得较好的部分', items: src.strengths || [], emptyText: EMPTY_TEXT.strengths },
    { key: 'issues', title: '需要改进', items: src.issues || [], emptyText: EMPTY_TEXT.issues },
    { key: 'suggestions', title: '后续建议', items: src.suggestions || [], emptyText: EMPTY_TEXT.suggestions },
  ]
}

const TIME_FMT = new Intl.DateTimeFormat('zh-CN', {
  month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
})

/** 时间格式化；坏数据返回空串 */
export function fmtDateTime(value) {
  if (value == null || value === '') return ''
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? '' : TIME_FMT.format(d)
}
