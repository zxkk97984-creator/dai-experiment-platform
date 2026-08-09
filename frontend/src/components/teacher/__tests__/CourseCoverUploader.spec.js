// 课程封面上传组件：选择/拖拽、本地预览、进度、取消、移除与错误提示
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const coursesMock = vi.hoisted(() => ({
  uploadCourseCover: vi.fn(),
  deleteCourseCover: vi.fn(),
}))

vi.mock('../../../api/courses.js', () => ({ coursesAPI: coursesMock }))

import CourseCoverUploader from '../CourseCoverUploader.vue'

const course = (cover = null) => ({ id: 7, title: '测试课程', cover })

const pngFile = () => new File(['x'.repeat(100)], 'cover.png', { type: 'image/png' })

const httpError = (status, code, message) =>
  Object.assign(new Error(`http ${status}`), {
    response: { status, data: { detail: { code, message } } },
  })

function mountUploader(c = course()) {
  return mount(CourseCoverUploader, {
    props: { courseId: 7, course: c },
    global: { stubs: { AppIcon: { template: '<i />' } } },
  })
}

function selectFile(wrapper, file = pngFile()) {
  const input = wrapper.get('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: [file] })
  return input.trigger('change')
}

beforeEach(() => {
  vi.clearAllMocks()
  coursesMock.uploadCourseCover.mockReset()
  coursesMock.deleteCourseCover.mockReset()
  URL.createObjectURL = vi.fn(() => 'blob:mock-preview')
  URL.revokeObjectURL = vi.fn()
})

describe('CourseCoverUploader 文件选择与校验', () => {
  it('accept 仅允许 jpg/jpeg/png/webp/gif', () => {
    const wrapper = mountUploader()
    const accept = wrapper.get('input[type="file"]').attributes('accept')
    expect(accept).toContain('.jpg')
    expect(accept).toContain('.jpeg')
    expect(accept).toContain('.png')
    expect(accept).toContain('.webp')
    expect(accept).toContain('.gif')
    expect(accept).not.toContain('.svg')
  })

  it('点击选择文件触发上传，FormData 字段名为 file', async () => {
    coursesMock.uploadCourseCover.mockResolvedValue({ data: course('covers/7/abc.png') })
    const wrapper = mountUploader()
    await selectFile(wrapper)

    expect(coursesMock.uploadCourseCover).toHaveBeenCalledTimes(1)
    const [courseId, file] = coursesMock.uploadCourseCover.mock.calls[0]
    expect(courseId).toBe(7)
    expect(file).toBeInstanceOf(File)
    expect(file.name).toBe('cover.png')
    await flushPromises()
  })

  it('拖拽文件同样触发上传', async () => {
    coursesMock.uploadCourseCover.mockResolvedValue({ data: course('covers/7/abc.png') })
    const wrapper = mountUploader()
    await wrapper
      .get('.cover-dropzone')
      .trigger('drop', { dataTransfer: { files: [pngFile()] } })

    expect(coursesMock.uploadCourseCover).toHaveBeenCalledTimes(1)
    await flushPromises()
  })

  it('客户端拒绝超过 5 MiB 的文件并显示明确提示', async () => {
    const wrapper = mountUploader()
    const big = new File(['x'.repeat(5 * 1024 * 1024 + 1)], 'big.png', { type: 'image/png' })
    await selectFile(wrapper, big)

    expect(coursesMock.uploadCourseCover).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('封面图片超过 5 MB 大小限制')
  })

  it('客户端拒绝明显错误 MIME 并显示明确提示', async () => {
    const wrapper = mountUploader()
    await selectFile(wrapper, new File(['x'], 'a.exe', { type: 'application/octet-stream' }))

    expect(coursesMock.uploadCourseCover).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('仅支持 JPG / PNG / WebP / GIF 图片')
  })
})

describe('CourseCoverUploader 预览、进度与取消', () => {
  it('选择后立即生成本地预览对象 URL', async () => {
    let resolveUpload
    coursesMock.uploadCourseCover.mockReturnValue(new Promise((r) => { resolveUpload = r }))
    const wrapper = mountUploader()
    await selectFile(wrapper)
    await flushPromises()

    // 上传挂起期间本地预览立即可见
    expect(URL.createObjectURL).toHaveBeenCalled()
    expect(wrapper.get('.cover-preview__img').attributes('src')).toBe('blob:mock-preview')
    resolveUpload({ data: course('covers/7/abc.png') })
    await flushPromises()
    wrapper.unmount()
  })

  it('上传进度根据 loaded / total 更新', async () => {
    let progressCb
    coursesMock.uploadCourseCover.mockImplementation((_id, _file, { onUploadProgress }) => {
      progressCb = onUploadProgress
      return new Promise(() => {}) // 挂起上传，便于观察进度
    })
    const wrapper = mountUploader()
    await selectFile(wrapper)
    await flushPromises()

    progressCb({ loaded: 25, total: 100 })
    await flushPromises()
    expect(wrapper.text()).toContain('25%')
    progressCb({ loaded: 80, total: 100 })
    await flushPromises()
    expect(wrapper.text()).toContain('80%')
    wrapper.unmount()
  })

  it('取消调用 AbortController.abort()', async () => {
    // 模拟 Axios：signal 中止后上传 Promise 以 ERR_CANCELED 拒绝
    coursesMock.uploadCourseCover.mockImplementation((_id, _file, { signal }) =>
      new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => {
          const err = new Error('canceled')
          err.code = 'ERR_CANCELED'
          reject(err)
        })
      }),
    )
    const wrapper = mountUploader()
    await selectFile(wrapper)
    await flushPromises()

    const signal = coursesMock.uploadCourseCover.mock.calls[0][2].signal
    expect(signal.aborted).toBe(false)
    await wrapper.get('.cover-cancel-btn').trigger('click')
    expect(signal.aborted).toBe(true)
    await flushPromises()
    expect(wrapper.text()).toContain('上传已取消')
    wrapper.unmount()
  })
})

describe('CourseCoverUploader 上传结果与错误', () => {
  it('上传成功发出 updated 事件，参数为 API 返回课程', async () => {
    const updated = course('covers/7/abc.png')
    coursesMock.uploadCourseCover.mockResolvedValue({ data: updated })
    const wrapper = mountUploader()
    await selectFile(wrapper)
    await flushPromises()

    expect(wrapper.emitted('updated')).toBeTruthy()
    expect(wrapper.emitted('updated')[0][0]).toEqual(updated)
    // 上传期间 busy-change 先 true 后 false
    expect(wrapper.emitted('busy-change')[0][0]).toBe(true)
    expect(wrapper.emitted('busy-change')[1][0]).toBe(false)
  })

  it('413 超限错误显示明确中文提示', async () => {
    coursesMock.uploadCourseCover.mockRejectedValue(httpError(413, 'COVER_TOO_LARGE', '封面文件超过 5 MB 大小限制'))
    const wrapper = mountUploader()
    await selectFile(wrapper)
    await flushPromises()

    expect(wrapper.text()).toContain('封面图片超过 5 MB 大小限制')
  })

  it('415 魔数错误显示明确中文提示', async () => {
    coursesMock.uploadCourseCover.mockRejectedValue(httpError(415, 'COVER_CONTENT_INVALID', '图片文件内容格式校验失败'))
    const wrapper = mountUploader()
    await selectFile(wrapper)
    await flushPromises()

    expect(wrapper.text()).toContain('图片内容格式校验失败')
  })

  it('415 扩展名/MIME 错误显示明确中文提示', async () => {
    coursesMock.uploadCourseCover.mockRejectedValue(httpError(415, 'COVER_TYPE_UNSUPPORTED', '仅支持 JPG / PNG / WebP / GIF 图片'))
    const wrapper = mountUploader()
    await selectFile(wrapper)
    await flushPromises()

    expect(wrapper.text()).toContain('仅支持 JPG / PNG / WebP / GIF 图片')
  })

  it('400 空文件错误显示后端提示', async () => {
    coursesMock.uploadCourseCover.mockRejectedValue(httpError(400, 'COVER_FILE_EMPTY', '图片文件为空'))
    const wrapper = mountUploader()
    await selectFile(wrapper)
    await flushPromises()

    expect(wrapper.text()).toContain('图片文件为空')
  })

  it('网络失败显示通用中文提示', async () => {
    coursesMock.uploadCourseCover.mockRejectedValue(new Error('network down'))
    const wrapper = mountUploader()
    await selectFile(wrapper)
    await flushPromises()

    expect(wrapper.text()).toContain('封面上传失败，请重试')
  })

  it('上传失败不发出 updated 事件', async () => {
    coursesMock.uploadCourseCover.mockRejectedValue(httpError(415, 'COVER_CONTENT_INVALID', 'x'))
    const wrapper = mountUploader()
    await selectFile(wrapper)
    await flushPromises()

    expect(wrapper.emitted('updated')).toBeFalsy()
  })
})

describe('CourseCoverUploader 移除封面', () => {
  it('已有封面显示“移除封面”按钮，无封面时不显示', () => {
    const withCover = mountUploader(course('covers/7/abc.png'))
    expect(withCover.find('.cover-remove-btn').exists()).toBe(true)
    withCover.unmount()

    const without = mountUploader(course(null))
    expect(without.find('.cover-remove-btn').exists()).toBe(false)
  })

  it('移除成功发出 updated，值为 { ...course, cover: null }', async () => {
    coursesMock.deleteCourseCover.mockResolvedValue({})
    const wrapper = mountUploader(course('covers/7/abc.png'))
    await wrapper.get('.cover-remove-btn').trigger('click')
    await flushPromises()

    expect(coursesMock.deleteCourseCover).toHaveBeenCalledWith(7)
    const emitted = wrapper.emitted('updated')[0][0]
    expect(emitted).toEqual({ id: 7, title: '测试课程', cover: null })
  })

  it('移除失败显示明确错误且不发出 updated', async () => {
    coursesMock.deleteCourseCover.mockRejectedValue(httpError(403, 'FORBIDDEN', '没有权限管理该课程'))
    const wrapper = mountUploader(course('covers/7/abc.png'))
    await wrapper.get('.cover-remove-btn').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('updated')).toBeFalsy()
    expect(wrapper.text()).toContain('无权修改该课程的封面')
  })
})

describe('CourseCoverUploader 生命周期与表单安全', () => {
  it('卸载时取消请求并释放本地预览对象 URL', async () => {
    coursesMock.uploadCourseCover.mockReturnValue(new Promise(() => {}))
    const wrapper = mountUploader()
    await selectFile(wrapper)
    await flushPromises()

    const signal = coursesMock.uploadCourseCover.mock.calls[0][2].signal
    wrapper.unmount()
    expect(signal.aborted).toBe(true)
    expect(URL.revokeObjectURL).toHaveBeenCalled()
  })

  it('组件内所有按钮均为 type="button"，不会提交外层课程设置表单', async () => {
    coursesMock.uploadCourseCover.mockResolvedValue({ data: course('covers/7/abc.png') })
    const wrapper = mountUploader(course('covers/7/abc.png'))
    await wrapper.get('.cover-remove-btn').trigger('click')
    await flushPromises()

    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBeGreaterThan(0)
    for (const btn of buttons) {
      expect(btn.attributes('type')).toBe('button')
    }
  })

  it('上传说明包含格式、大小与公开属性提示', () => {
    const wrapper = mountUploader()
    expect(wrapper.text()).toContain('支持 JPG、PNG、WebP、GIF，最大 5 MB')
    expect(wrapper.text()).toContain('公开显示')
  })
})
