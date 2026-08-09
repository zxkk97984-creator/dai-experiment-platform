// coursesAPI 接口契约：路径、payload、multipart 与超时配置
import { beforeEach, describe, expect, it, vi } from 'vitest'

const client = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('../client.js', () => ({ default: client }))

import { coursesAPI } from '../courses.js'

describe('coursesAPI 课程白名单', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('listWhitelist 使用 GET /courses/{id}/whitelist 并透传分页/搜索参数', () => {
    coursesAPI.listWhitelist(7, { page: 2, page_size: 50, q: '张三' })

    expect(client.get).toHaveBeenCalledWith('/courses/7/whitelist', {
      params: { page: 2, page_size: 50, q: '张三' },
    })
  })

  it('addWhitelistStudent 使用 POST /courses/{id}/whitelist 且 payload 为 student_id', () => {
    coursesAPI.addWhitelistStudent(7, 123)

    expect(client.post).toHaveBeenCalledWith('/courses/7/whitelist', { student_id: 123 })
  })

  it('removeWhitelistStudent 使用 DELETE /courses/{id}/whitelist/{student_id}', () => {
    coursesAPI.removeWhitelistStudent(7, 123)

    expect(client.delete).toHaveBeenCalledWith('/courses/7/whitelist/123')
  })
})

describe('coursesAPI 教师视频上传', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('uploadLessonVideo 使用 PUT /lessons/{id}/video-file 且 FormData 字段名为 file', () => {
    const file = new File(['x'], 'demo.mp4', { type: 'video/mp4' })
    coursesAPI.uploadLessonVideo(9, file)

    const [path, body, config] = client.put.mock.calls[0]
    expect(path).toBe('/lessons/9/video-file')
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('file')).toBe(file)
    // multipart 覆盖实例 JSON Content-Type，由 Axios/浏览器生成 boundary
    expect(config.headers['Content-Type']).toBeUndefined()
  })

  it('uploadLessonVideo 单独配置 600 秒超时并透传进度回调与取消信号', () => {
    const onUploadProgress = vi.fn()
    const signal = new AbortController().signal
    coursesAPI.uploadLessonVideo(9, new File(['x'], 'a.mp4', { type: 'video/mp4' }), {
      onUploadProgress,
      signal,
    })

    const config = client.put.mock.calls[0][2]
    expect(config.timeout).toBe(600000)
    expect(config.onUploadProgress).toBe(onUploadProgress)
    expect(config.signal).toBe(signal)
  })

  it('deleteLessonVideo 使用 DELETE /lessons/{id}/video-file', () => {
    coursesAPI.deleteLessonVideo(9)

    expect(client.delete).toHaveBeenCalledWith('/lessons/9/video-file')
  })

  it('getLessonVideoPlaybackUrl 使用 GET /lessons/{id}/video-playback-url', () => {
    coursesAPI.getLessonVideoPlaybackUrl(9)

    expect(client.get).toHaveBeenCalledWith('/lessons/9/video-playback-url')
  })
})

describe('coursesAPI 课程封面上传', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('uploadCourseCover 使用 PUT /courses/{id}/cover 且 FormData 字段名为 file', () => {
    const file = new File(['x'], 'cover.png', { type: 'image/png' })
    coursesAPI.uploadCourseCover(9, file)

    const [path, body, config] = client.put.mock.calls[0]
    expect(path).toBe('/courses/9/cover')
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('file')).toBe(file)
    // multipart 覆盖实例 JSON Content-Type，由 Axios/浏览器生成 boundary
    expect(config.headers['Content-Type']).toBeUndefined()
  })

  it('uploadCourseCover 单独配置 600 秒超时并透传进度回调与取消信号', () => {
    const onUploadProgress = vi.fn()
    const signal = new AbortController().signal
    coursesAPI.uploadCourseCover(9, new File(['x'], 'a.png', { type: 'image/png' }), {
      onUploadProgress,
      signal,
    })

    const config = client.put.mock.calls[0][2]
    expect(config.timeout).toBe(600000)
    expect(config.onUploadProgress).toBe(onUploadProgress)
    expect(config.signal).toBe(signal)
  })

  it('deleteCourseCover 使用 DELETE /courses/{id}/cover', () => {
    coursesAPI.deleteCourseCover(9)

    expect(client.delete).toHaveBeenCalledWith('/courses/9/cover')
  })
})
