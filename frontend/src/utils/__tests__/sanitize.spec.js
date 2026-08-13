/**
 * HTML 安全清洗测试 — TASK-002（F-17/F-18 公告修补验收）
 *
 * 覆盖真实渲染管线：raw markdown → marked → sanitizeHtml → v-html
 * （MarkdownCell / QeMarkdownEditor / SubmissionSnapshotCell 同款链路），
 * 断言脚本、事件处理器、危险协议与禁用标签被清除，允许策略保持原样。
 */
import { describe, it, expect } from 'vitest'
import { marked } from 'marked'
import { sanitizeHtml } from '../sanitize.js'

const renderMarkdown = (src) => sanitizeHtml(marked.parse(src, { async: false }))

describe('sanitizeHtml 输入边界', () => {
  it('非字符串输入返回空字符串', () => {
    expect(sanitizeHtml()).toBe('')
    expect(sanitizeHtml(null)).toBe('')
    expect(sanitizeHtml(undefined)).toBe('')
    expect(sanitizeHtml(42)).toBe('')
    expect(sanitizeHtml({})).toBe('')
  })

  it('空字符串原样返回', () => {
    expect(sanitizeHtml('')).toBe('')
  })
})

describe('sanitizeHtml XSS 防护', () => {
  it('清除 script 标签', () => {
    const out = sanitizeHtml('<p>正常</p><script>alert(1)</script>')
    expect(out).not.toContain('<script')
    expect(out).not.toContain('alert(1)')
    expect(out).toContain('<p>正常</p>')
  })

  it('清除内联事件处理器', () => {
    const out = sanitizeHtml('<img src="x.png" onerror="steal()">')
    expect(out).not.toContain('onerror')
  })

  it('清除 javascript: 协议链接', () => {
    const out = sanitizeHtml('<a href="javascript:alert(1)">点我</a>')
    expect(out).not.toContain('javascript:')
    expect(out).toContain('点我')
  })

  it('清除 javascript: 协议的图片地址', () => {
    const out = sanitizeHtml('<img src="javascript:alert(1)">')
    expect(out).not.toContain('javascript:')
  })

  it('清除 iframe/object/embed 等未允许标签', () => {
    const out = sanitizeHtml('<iframe src="https://evil.example"></iframe><object data="x"></object><embed src="y">')
    expect(out).not.toContain('<iframe')
    expect(out).not.toContain('<object')
    expect(out).not.toContain('<embed')
  })

  it('清除 style 标签但保留文本内容', () => {
    const out = sanitizeHtml('<style>body{display:none}</style><p>正文</p>')
    expect(out).not.toContain('<style')
    expect(out).toContain('正文')
  })

  it('保留允许的富文本标签', () => {
    const out = sanitizeHtml('<p>段<b>粗</b><i>斜</i><a href="https://example.com" title="t" target="_blank">链</a></p>')
    expect(out).toContain('<b>粗</b>')
    expect(out).toContain('<i>斜</i>')
    expect(out).toContain('href="https://example.com"')
  })

  it('html 实体逃逸的脚本不复活', () => {
    const out = sanitizeHtml('<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>')
    expect(out).toContain('&lt;script&gt;')
    expect(out).not.toContain('<script>')
  })
})

describe('markdown → sanitizeHtml 渲染管线（v-html 前）', () => {
  it('markdown 内嵌 HTML 脚本被清除', () => {
    const out = renderMarkdown('# 标题\n\n<script>alert(1)</script>')
    expect(out).toContain('<h1>标题</h1>')
    expect(out).not.toContain('<script')
  })

  it('markdown 内嵌 HTML 图片事件处理器被清除', () => {
    const out = renderMarkdown('![x](img.png)\n\n<img src="x.png" onerror="alert(1)">')
    expect(out).not.toContain('onerror')
    expect(out).not.toContain('alert(1)')
  })

  it('markdown 链接 javascript: 协议被清除', () => {
    const out = renderMarkdown('[点我](javascript:alert(1))')
    expect(out).not.toContain('javascript:')
  })

  it('markdown 链接 data: 协议被清除', () => {
    const out = renderMarkdown('[点我](data:text/html;base64,PHNjcmlwdD4=)')
    expect(out).not.toContain('data:')
  })

  it('合法 markdown 结构完整保留（标题/粗体/代码/列表）', () => {
    const src = '# 标题\n\n**粗体** 与 `代码`\n\n- 项1\n- 项2\n'
    const out = renderMarkdown(src)
    expect(out).toContain('<h1>标题</h1>')
    expect(out).toContain('<strong>粗体</strong>')
    expect(out).toContain('<code>代码</code>')
    expect(out).toContain('<li>项1</li>')
    expect(out).toContain('<li>项2</li>')
  })

  it('外链 rel/target 行为保持既有策略不变', () => {
    const out = renderMarkdown('[外链](https://example.com)')
    expect(out).toContain('https://example.com')
  })
})
