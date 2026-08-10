/** 展示格式化工具测试：日期时间的空值/无效值/秒级精度处理 */
import { describe, it, expect } from 'vitest'
import { formatDate, formatDateTime, formatDuration, formatBytes } from '../format.js'

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

  it('输出 2026-08-10 08:30 样式', () => {
    expect(formatDateTime('2026-08-10T08:30:00+08:00')).toBe('2026-08-10 08:30')
  })

  it('seconds 选项开启时包含秒', () => {
    expect(formatDateTime('2026-08-10T08:00:30+08:00', { seconds: true })).toMatch(/30/)
    expect(formatDateTime('2026-08-10T08:00:30+08:00', { seconds: true })).toBe('2026-08-10 08:00:30')
    expect(formatDateTime('2026-08-10T08:00:30+08:00')).not.toMatch(/30/)
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
