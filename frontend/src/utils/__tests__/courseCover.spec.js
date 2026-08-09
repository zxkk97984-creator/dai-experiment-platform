// getCourseCoverUrl：受管存储 key 转公开媒体 URL；历史 URL 原样兼容
import { describe, expect, it } from 'vitest'

import { getCourseCoverUrl } from '../courseCover.js'

describe('getCourseCoverUrl 受管存储 key', () => {
  it('covers/ 开头的新 key 转为公开媒体 URL，v 参数为编码后的 key', () => {
    expect(getCourseCoverUrl({ id: 42, cover: 'covers/42/abc.webp' })).toBe(
      '/api/v1/media/course-covers/42?v=covers%2F42%2Fabc.webp',
    )
  })

  it('课程 id 是字符串时同样可用', () => {
    expect(getCourseCoverUrl({ id: '42', cover: 'covers/42/abc.png' })).toBe(
      '/api/v1/media/course-covers/42?v=covers%2F42%2Fabc.png',
    )
  })
})

describe('getCourseCoverUrl 历史 URL 兼容', () => {
  it('cover 为空返回空字符串（无封面占位）', () => {
    expect(getCourseCoverUrl({ id: 42, cover: '' })).toBe('')
    expect(getCourseCoverUrl({ id: 42, cover: null })).toBe('')
    expect(getCourseCoverUrl({ id: 42 })).toBe('')
    expect(getCourseCoverUrl(null)).toBe('')
  })

  it('历史 http(s) URL 原样返回', () => {
    const cover = 'https://legacy.example.com/course/42/cover.jpg'
    expect(getCourseCoverUrl({ id: 42, cover })).toBe(cover)
    expect(getCourseCoverUrl({ id: 42, cover: 'http://legacy.example.com/a.png' })).toBe(
      'http://legacy.example.com/a.png',
    )
  })

  it('协议相对与根路径 URL 原样返回', () => {
    expect(getCourseCoverUrl({ id: 42, cover: '//cdn.example.com/a.jpg' })).toBe(
      '//cdn.example.com/a.jpg',
    )
    expect(getCourseCoverUrl({ id: 42, cover: '/static/covers/a.jpg' })).toBe(
      '/static/covers/a.jpg',
    )
  })

  it('未识别的历史相对路径原样返回，由图片加载失败回退兜底', () => {
    expect(getCourseCoverUrl({ id: 42, cover: 'legacy/covers/a.jpg' })).toBe(
      'legacy/covers/a.jpg',
    )
  })
})
