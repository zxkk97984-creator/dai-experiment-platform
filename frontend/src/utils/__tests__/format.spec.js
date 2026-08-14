/** 展示格式化工具测试：日期时间的空值/无效值/秒级精度处理 */
import { describe, it, expect } from 'vitest'
import { formatDate, formatDateTime, formatDuration, formatBytes, fromDateTimeLocal, toDateTimeLocal } from '../format.js'

describe('formatDateTime', () => {
  it('空值返回占位符', () => {
    expect(formatDateTime()).toBe('—')
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime('')).toBe('—')
  })

  it('无效日期返回占位符而非 Invalid Date', () => {
    expect(formatDateTime('not-a-date')).toBe('—')
    expect(formatDateTime('2026-13-99')).toBe('—')
  })

  // 时区无关断言（2026-08 修复 CI 红灯）：
  // formatDateTime 按浏览器本地时区渲染，CI runner 是 UTC、开发机是 UTC+8，
  // 直接断言某台机器的墙钟会随 TZ 漂移。改为断言「同一瞬间的不同时区表示
  // 必须渲染成同一个字符串」+ 不受 TZ 影响的形状（分钟/秒不受时区偏移改变）。
  it('输出 2026-08-10 08:30 样式', () => {
    const fromUtc = formatDateTime('2026-08-10T00:30:00Z')
    const fromOffset = formatDateTime('2026-08-10T08:30:00+08:00')
    expect(fromUtc).toBe(fromOffset)
    expect(fromUtc).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:30$/)
  })

  it('seconds 选项开启时包含秒', () => {
    const withSeconds = formatDateTime('2026-08-10T08:00:30+08:00', { seconds: true })
    const utcWithSeconds = formatDateTime('2026-08-10T00:00:30Z', { seconds: true })
    expect(withSeconds).toBe(utcWithSeconds)
    expect(withSeconds).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:30$/)
    expect(formatDateTime('2026-08-10T08:00:30+08:00')).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)
  })
})

describe('datetime-local conversion', () => {
  it('round-trips a local input through an ISO timestamp', () => {
    const local = '2026-08-12T18:30'
    expect(toDateTimeLocal(fromDateTimeLocal(local))).toBe(local)
  })

  it('treats timezone-less API datetimes as UTC before converting to local time', () => {
    expect(toDateTimeLocal('2026-08-12T10:30:00')).toBe(toDateTimeLocal('2026-08-12T10:30:00Z'))
    expect(formatDateTime('2026-08-12T10:30:00')).toBe(formatDateTime('2026-08-12T10:30:00Z'))
  })

  it('uses empty/null values for an unset deadline', () => {
    expect(toDateTimeLocal(null)).toBe('')
    expect(fromDateTimeLocal('')).toBeNull()
  })
})

describe('formatDate', () => {
  it('空值返回占位符', () => {
    expect(formatDate()).toBe('—')
    expect(formatDate('')).toBe('—')
  })
})

describe('formatDuration', () => {
  it('分钟与小时换算', () => {
    expect(formatDuration(45)).toBe('45 分钟')
    expect(formatDuration(90)).toBe('1 小时 30 分钟')
    expect(formatDuration(0)).toBe('0 分钟')
    expect(formatDuration()).toBe('—')
  })
})

describe('formatBytes', () => {
  it('单位换算', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(1024)).toBe('1.0 KB')
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB')
  })
})
