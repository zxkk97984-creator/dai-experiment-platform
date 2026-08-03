// CodeViewer：只读代码展示（CodeMirror）正常路径测试。
// jsdom 中动态 import 可加载 CodeMirror（与 CodeCell.spec.js 同一模式）。

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import CodeViewer from '../CodeViewer.vue'

const wrappers = []

async function waitForCodeMirror(wrapper) {
  await flushPromises()
  await vi.waitFor(() => {
    expect(wrapper.find('.cm-content').exists()).toBe(true)
  })
}

function mountViewer(props = {}) {
  const wrapper = mount(CodeViewer, {
    props: { code: 'def is_valid(s):\n    return True\n', ...props },
  })
  wrappers.push(wrapper)
  return wrapper
}

beforeEach(() => {
  // 复制：优先走 clipboard API
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
    configurable: true,
  })
})

afterEach(() => {
  for (const wrapper of wrappers.splice(0)) {
    wrapper.unmount()
  }
})

describe('CodeViewer', () => {
  it('CodeMirror 加载且只读', async () => {
    const wrapper = mountViewer()
    await waitForCodeMirror(wrapper)

    expect(wrapper.get('.cm-content').attributes('contenteditable')).toBe('false')
    expect(wrapper.find('.cm-lineNumbers').exists()).toBe(true)
    expect(wrapper.get('.cm-content').text()).toContain('def is_valid')
  })

  it('工具栏：语言标签、复制、下载按钮', async () => {
    const wrapper = mountViewer()
    await waitForCodeMirror(wrapper)

    expect(wrapper.text()).toContain('Python')
    expect(wrapper.text()).toContain('复制代码')
    expect(wrapper.text()).toContain('下载代码')
  })

  it('复制代码调用 clipboard 并给出成功提示', async () => {
    const wrapper = mountViewer()
    await waitForCodeMirror(wrapper)

    await wrapper.findAll('button').find((b) => b.text().includes('复制代码')).trigger('click')
    await flushPromises()

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('def is_valid(s):\n    return True\n')
    expect(wrapper.text()).toContain('已复制')
  })

  it('clipboard 不可用时降级复制并提示', async () => {
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
    const wrapper = mountViewer()
    await waitForCodeMirror(wrapper)

    await wrapper.findAll('button').find((b) => b.text().includes('复制代码')).trigger('click')
    await flushPromises()

    // 降级路径：不抛异常，仍有反馈提示（execCommand 在 jsdom 返回 false → 失败文案或手动选择提示）
    expect(wrapper.find('.code-viewer__toast').exists()).toBe(true)
  })

  it('下载代码：生成 Blob 文件并回收 URL', async () => {
    const createObjectURL = vi.fn(() => 'blob:mock')
    const revokeObjectURL = vi.fn()
    const clickSpy = vi.fn()
    Object.defineProperty(URL, 'createObjectURL', { value: createObjectURL, configurable: true })
    Object.defineProperty(URL, 'revokeObjectURL', { value: revokeObjectURL, configurable: true })
    Object.defineProperty(HTMLAnchorElement.prototype, 'click', { value: clickSpy, configurable: true })

    const wrapper = mountViewer({ filename: 'sub:mission' })
    await waitForCodeMirror(wrapper)

    await wrapper.findAll('button').find((b) => b.text().includes('下载代码')).trigger('click')
    await flushPromises()

    expect(createObjectURL).toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock')
    expect(wrapper.text()).toContain('已下载')
  })

  it('highlightLines 渲染行高亮装饰', async () => {
    const wrapper = mountViewer({ highlightLines: [1] })
    await waitForCodeMirror(wrapper)

    await wrapper.setProps({ highlightLines: [1, 2] })
    await flushPromises()

    expect(wrapper.find('.cm-line-highlight').exists()).toBe(true)
  })

  it('focusLine：滚动到行并标记 active（越界忽略不抛异常）', async () => {
    const wrapper = mountViewer()
    await waitForCodeMirror(wrapper)

    expect(() => wrapper.vm.focusLine(1)).not.toThrow()
    expect(() => wrapper.vm.focusLine(999)).not.toThrow()
    expect(() => wrapper.vm.focusLine('abc')).not.toThrow()
    await flushPromises()

    expect(wrapper.find('.cm-line-active').exists()).toBe(true)
  })

  it('active 行号小于证据行号时装饰仍按 from 排序（浏览器 RangeSet 严格性）', async () => {
    const twelveLines = Array.from({ length: 12 }, (_, i) => `line ${i + 1}`).join('\n')
    const wrapper = mount(CodeViewer, {
      props: { code: twelveLines, highlightLines: [10, 11] },
    })
    wrappers.push(wrapper)
    await waitForCodeMirror(wrapper)

    // active=4 位于 lines=[10,11] 之前，必须排序后才能 Decoration.set
    expect(() => wrapper.vm.focusLine(4)).not.toThrow()
    await flushPromises()
    expect(wrapper.find('.cm-line-active').exists()).toBe(true)
    expect(wrapper.find('.cm-line-highlight').exists()).toBe(true)
  })

  it('编辑器卸载后不再执行滚动', async () => {
    const wrapper = mountViewer()
    await waitForCodeMirror(wrapper)
    const viewer = wrapper.vm
    wrapper.unmount()
    wrappers.splice(wrappers.indexOf(wrapper), 1)

    expect(() => viewer.focusLine(1)).not.toThrow()
  })
})
