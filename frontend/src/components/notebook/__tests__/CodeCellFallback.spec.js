import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import CodeCell from '../CodeCell.vue'

// 模拟 CodeMirror 运行时不可用（任何导出访问即抛错）→ 组件必须走 textarea fallback
vi.mock('@codemirror/view', () => new Proxy({}, {
  get: () => { throw new Error('CodeMirror unavailable') },
}))

function makeCell(overrides = {}) {
  return {
    id: 'c1',
    type: 'code',
    source: 'print(1)',
    order: 1,
    student_editable: true,
    outputs: null,
    ...overrides,
  }
}

describe('CodeCell fallback（CodeMirror 加载失败时）', () => {
  it('falls back to the textarea and keeps the light theme marker', async () => {
    const wrapper = mount(CodeCell, { props: { cell: makeCell() } })
    await flushPromises()

    expect(wrapper.find('.cm-editor').exists()).toBe(false)
    expect(wrapper.get('.code-textarea').exists()).toBe(true)
    // 浅色语义标记在 fallback 下同样存在（样式语义由 data-code-theme 声明）
    expect(wrapper.attributes('data-code-theme')).toBe('light')
  })

  it('still allows executing the cell source in fallback mode', async () => {
    const wrapper = mount(CodeCell, { props: { cell: makeCell() } })
    await flushPromises()

    await wrapper.get('.btn-run').trigger('click')
    expect(wrapper.emitted('execute')).toEqual([['c1']])
  })
})
