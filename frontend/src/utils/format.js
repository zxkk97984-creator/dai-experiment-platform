const NAIVE_ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?$/

export function parseApiDateTime(value) {
  // MySQL/SQLite may return UTC database values without a timezone suffix.
  // The backend comparison contract treats these naive values as UTC, so the
  // browser must do the same before formatting them in the user's local zone.
  const normalized = typeof value === 'string' && NAIVE_ISO_DATETIME.test(value)
    ? `${value}Z`
    : value
  return new Date(normalized)
}

export function formatDate(isoStr) {
  if (!isoStr) return '—'
  const d = parseApiDateTime(isoStr)
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

export function formatDateTime(value, { seconds = false } = {}) {
  if (!value) return '—'
  const date = parseApiDateTime(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
    ...(seconds ? { second: '2-digit' } : {}),
    hour12: false,
  }).format(date).replaceAll('/', '-')
}

export function toDateTimeLocal(value) {
  if (!value) return ''
  const date = parseApiDateTime(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (part) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function fromDateTimeLocal(value) {
  if (!value) return null
  // datetime-local deliberately has no timezone; the browser must interpret
  // it in the teacher's local zone before we serialize an explicit UTC ISO.
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

export function formatDuration(minutes) {
  if (!minutes && minutes !== 0) return '—'
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h > 0) return `${h} 小时 ${m} 分钟`
  return `${m} 分钟`
}

export function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let val = bytes
  while (val >= 1024 && i < units.length - 1) { val /= 1024; i++ }
  return `${val.toFixed(i > 0 ? 1 : 0)} ${units[i]}`
}

export function timeAgo(isoStr) {
  if (!isoStr) return '—'
  const diff = Date.now() - parseApiDateTime(isoStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} 天前`
  return formatDate(isoStr)
}
