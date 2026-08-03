// CodeViewer fallback：CodeMirror 模块加载失败时降级为只读 pre。
// 动态 import 的模块 mock 是文件级作用域，故单独一个测试文件。

import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import CodeViewer from '../CodeViewer.vue'

vi.mock('@codemirror/view', () => {
  throw new Error('mock load failure')
})

async function waitFallback(wrapper) {
  await flushPromises()
  await vi.waitFor(() => {
    expect(wrapper.find('.code-viewer__fallback').exists()).toBe(true)
  })
}

describe('CodeViewer fallback', () => {
  it('CodeMirror 加载失败时降级为只读 pre，代码仍可见', async () => {
    const wrapper = mount(CodeViewer, {
      props: { code: 'print("hi")\n' },
    })

    await waitFallback(wrapper)

    const pre = wrapper.get('.code-viewer__fallback pre')
    expect(pre.text()).toContain('print("hi")')
    // 工具栏功能不因降级缺失
    expect(wrapper.text()).toContain('复制代码')
    expect(wrapper.text()).toContain('下载代码')
  })
})
