import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MarkdownCell from '../MarkdownCell.vue'

describe('MarkdownCell', () => {
  it('sanitizes XSS in markdown source', () => {
    const wrapper = mount(MarkdownCell, {
      props: {
        cell: { id: 'm1', type: 'markdown', source: '<script>alert("xss")</script>' },
      },
    })
    const html = wrapper.find('.cell-body').html()
    // DOMPurify 移除 <script> 标签
    expect(html).not.toMatch(/<script[^>]*>/i)
    // onclick 等事件属性被移除
    expect(html).not.toMatch(/\son\w+=/i)
  })

  it('sanitizes event handler attributes', () => {
    const wrapper = mount(MarkdownCell, {
      props: {
        cell: { id: 'm2', type: 'markdown', source: '<img src=x onerror=alert(1)>' },
      },
    })
    const html = wrapper.find('.cell-body').html()
    // onerror 属性被移除
    expect(html).not.toMatch(/\sonerror\b/i)
    // javascript: URL 被移除
    expect(html).not.toMatch(/javascript:/i)
  })

  it('renders safe markdown', () => {
    const wrapper = mount(MarkdownCell, {
      props: {
        cell: { id: 'm3', type: 'markdown', source: '# Hello\n\n**bold** text' },
      },
    })
    const html = wrapper.find('.cell-body').html()
    expect(html).toContain('Hello')
    expect(html).toContain('bold')
  })

  it('renders fenced code blocks', () => {
    const wrapper = mount(MarkdownCell, {
      props: {
        cell: { id: 'm4', type: 'markdown', source: '```python\nprint("hi")\n```' },
      },
    })
    const pre = wrapper.find('.cell-body pre')
    expect(pre.exists()).toBe(true)
    expect(pre.text()).toContain('print("hi")')
  })

  it('sanitizes XSS attempts inside fenced code', () => {
    const wrapper = mount(MarkdownCell, {
      props: {
        cell: { id: 'm5', type: 'markdown', source: '```html\n<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n```' },
      },
    })
    const html = wrapper.find('.cell-body').html()
    // 围栏内容必须被转义为纯文本展示：不得出现可执行的 <script>/<img> 标签或事件属性
    // （marked 会把围栏内 HTML 转义为 &lt;...&gt;，因此「真实标签」才会被此断言拦下）
    expect(html).not.toMatch(/<(script|img)\b[^>]*>/i)
    expect(html).not.toMatch(/<[^>]*\son\w+=/i)
  })
})
