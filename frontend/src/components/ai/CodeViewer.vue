<script setup>
// CodeViewer：只读 Python 代码展示（CodeMirror 动态加载，失败降级为只读 pre）。
// 能力：语法高亮 + 行号 + 复制/下载 + 证据行高亮（highlightLines/activeLine）
//       + 行定位接口（scrollToLine/focusLine，1-based 行号，越界忽略）。

import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  code: { type: String, default: '' },
  /** 下载文件名（不含扩展名与非法字符） */
  filename: { type: String, default: 'submission' },
  /** 证据涉及的全部行（1-based），浅色高亮 */
  highlightLines: { type: Array, default: () => [] },
  /** 当前查看行（1-based），更强高亮 */
  activeLine: { type: [Number, null], default: null },
})

const editorEl = ref(null)
const cmLoaded = ref(false)
const toast = ref('')
let cmView = null
let highlightField = null
let setHighlights = null
let mark = null
let activeMark = null
let CmView = null
let toastTimer = null

// ── CodeMirror 初始化（动态 import，失败降级 pre） ──────────────
async function initCodeMirror() {
  try {
    const [
      { EditorView, lineNumbers, Decoration },
      { EditorState, StateEffect, StateField },
      { python },
      { HighlightStyle, syntaxHighlighting },
      { tags },
    ] = await Promise.all([
      import('@codemirror/view'),
      import('@codemirror/state'),
      import('@codemirror/lang-python'),
      import('@codemirror/language'),
      import('@lezer/highlight'),
    ])

    // V2 深墨松绿语法主题（与 dai-ds-v2.css 的 .code-panel 色板一致）
    const daiDarkHighlight = HighlightStyle.define([
      { tag: tags.comment, color: 'oklch(0.55 0.015 155)', fontStyle: 'italic' },
      { tag: tags.keyword, color: 'oklch(0.68 0.09 158)' },
      { tag: [tags.string, tags.special(tags.string)], color: 'oklch(0.72 0.11 80)' },
      { tag: [tags.number, tags.bool, tags.null], color: 'oklch(0.72 0.09 45)' },
      { tag: [tags.function(tags.variableName), tags.labelName], color: 'oklch(0.74 0.08 235)' },
      { tag: [tags.className, tags.typeName], color: 'oklch(0.78 0.015 155)' },
      { tag: tags.operator, color: 'oklch(0.72 0.015 155)' },
    ])

    CmView = EditorView
    mark = Decoration.mark({ class: 'cm-line-highlight' })
    activeMark = Decoration.mark({ class: 'cm-line-active' })
    setHighlights = StateEffect.define()
    highlightField = StateField.define({
      create: () => ({ ranges: [], active: null }),
      update(value, tr) {
        let v = value
        for (const e of tr.effects) {
          if (e.is(setHighlights)) v = e.value
        }
        // 在 update 阶段（tr.state.doc 可用）把 1-based 行号转成位置范围。
        // decorations.from 的 compute 在 state 创建阶段也会执行（此时无 view），
        // 因此 compute 只消费预存范围，绝不访问 view。
        // Decoration.set 要求 ranges 按 from 升序（active 行号可能小于证据行号）。
        const doc = tr.state.doc
        const ranges = []
        for (const n of v?.lines || []) {
          if (!Number.isInteger(n) || n < 1 || n > doc.lines) continue
          const line = doc.line(n)
          ranges.push(mark.range(line.from, line.to))
        }
        if (v?.active != null && v.active >= 1 && v.active <= doc.lines) {
          const line = doc.line(v.active)
          ranges.push(activeMark.range(line.from, line.to))
        }
        ranges.sort((a, b) => a.from - b.from)
        return { ...v, ranges }
      },
      provide: (f) => EditorView.decorations.from(f, (v) => Decoration.set(v?.ranges || [])),
    })

    const state = EditorState.create({
      doc: props.code,
      extensions: [
        lineNumbers(),
        python(),
        syntaxHighlighting(daiDarkHighlight),
        highlightField,
        EditorView.editable.of(false),
        EditorView.theme(
          {
            '&': { height: '100%', backgroundColor: 'oklch(0.225 0.018 155)', color: 'oklch(0.84 0.01 155)' },
            '.cm-scroller': { overflow: 'auto', fontFamily: 'var(--font-mono)', fontSize: '13px', lineHeight: '1.65' },
            '.cm-content': { caretColor: 'transparent' },
            '.cm-gutters': { backgroundColor: 'oklch(0.225 0.018 155)', color: 'oklch(0.48 0.015 155)', border: '0' },
            '.cm-activeLine': { backgroundColor: 'color-mix(in oklch, var(--accent) 8%, transparent)' },
            '.cm-activeLineGutter': { backgroundColor: 'transparent', color: 'var(--accent)' },
          },
          { dark: true },
        ),
      ],
    })
    cmView = new EditorView({ state, parent: editorEl.value })
    cmLoaded.value = true
  } catch (e) {
    // 与 CodeCell 一致：加载失败降级，记录原因便于排查
    console.warn('CodeViewer CodeMirror load failed:', e?.stack || e?.message || e)
    cmLoaded.value = false
  }
}

onMounted(initCodeMirror)

onBeforeUnmount(() => {
  if (cmView) {
    cmView.destroy()
    cmView = null
  }
  if (toastTimer) clearTimeout(toastTimer)
})

// 外部 code 变化同步（保留滚动位置，不重建编辑器）
watch(() => props.code, (val) => {
  if (cmView) {
    cmView.dispatch({ changes: { from: 0, to: cmView.state.doc.length, insert: val } })
  }
})

function applyHighlights() {
  if (!cmView) return
  cmView.dispatch({
    effects: setHighlights.of({ lines: props.highlightLines, active: props.activeLine }),
  })
}

watch(() => props.highlightLines, applyHighlights, { deep: true })
watch(() => props.activeLine, applyHighlights)

// ── 行定位接口 ──────────────────────────────────────────────────
function scrollToLine(line) {
  const view = cmView
  const n = Number(line)
  if (!view || !Number.isInteger(n) || n < 1 || n > view.state.doc.lines) return
  const pos = view.state.doc.line(n).from
  view.dispatch({ effects: CmView.scrollIntoView(pos, { y: 'center' }) })
}

function focusLine(line) {
  const n = Number(line)
  // 无效行直接忽略，不覆盖当前 active 标记
  if (!cmView || !Number.isInteger(n) || n < 1 || n > cmView.state.doc.lines) return
  scrollToLine(line)
  cmView.dispatch({
    effects: setHighlights.of({ lines: props.highlightLines, active: n }),
  })
}

defineExpose({ scrollToLine, focusLine })

// ── 复制 / 下载 ─────────────────────────────────────────────────
function showToast(text, ms = 2200) {
  toast.value = text
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value = ''
  }, ms)
}

async function copyCode() {
  let ok = false
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(props.code)
      ok = true
    } catch {
      ok = false
    }
  }
  if (!ok) {
    // 降级：临时 textarea + execCommand
    try {
      const ta = document.createElement('textarea')
      ta.value = props.code
      ta.setAttribute('readonly', '')
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      ok = document.execCommand('copy')
      ta.remove()
    } catch {
      ok = false
    }
  }
  showToast(ok ? '代码已复制' : '复制失败，请手动选择代码')
}

function safeFilename(name) {
  return String(name || 'submission').replace(/[\\/:*?"<>|\s]+/g, '_') || 'submission'
}

function downloadCode() {
  const blob = new Blob([props.code], { type: 'text/x-python;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${safeFilename(props.filename)}.py`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
  showToast('代码已下载')
}
</script>

<template>
  <div class="code-viewer">
    <div class="code-viewer__toolbar">
      <span class="code-viewer__lang">Python</span>
      <div class="code-viewer__actions">
        <button type="button" class="code-viewer__action" aria-label="复制代码" @click="copyCode">
          复制代码
        </button>
        <button type="button" class="code-viewer__action" aria-label="下载代码" @click="downloadCode">
          下载代码
        </button>
      </div>
    </div>

    <div class="code-viewer__body">
      <div ref="editorEl" class="code-viewer__editor">
        <div v-if="!cmLoaded" class="code-viewer__fallback">
          <pre class="code-viewer__fallback-pre"><code>{{ code }}</code></pre>
        </div>
      </div>
    </div>

    <p v-if="toast" class="code-viewer__toast" role="status">{{ toast }}</p>
  </div>
</template>

<style scoped>
/* V2 深墨松绿代码面板：视觉来自 dai-ds-v2.css 的 .code-panel 体系。 */
.code-viewer {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: oklch(0.225 0.018 155);
}

.code-viewer__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 38px;
  padding: 0 12px;
  border-bottom: 1px solid oklch(0.32 0.02 155);
  background: oklch(0.20 0.016 155);
}

.code-viewer__lang {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: 600;
  color: oklch(0.78 0.015 155);
}

.code-viewer__actions { display: flex; gap: 2px; }

.code-viewer__action {
  height: 28px;
  padding: 0 10px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: oklch(0.62 0.015 155);
  font-size: var(--text-xs);
  font-weight: 500;
  cursor: pointer;
}
.code-viewer__action:hover { background: oklch(0.32 0.02 155); color: oklch(0.86 0.015 155); }

.code-viewer__body {
  min-height: 240px;
  max-height: 560px;
  overflow: auto;
}

.code-viewer__editor { height: 100%; min-height: 240px; }
.code-viewer__editor :deep(.cm-editor) { height: 100%; }
.code-viewer__editor :deep(.cm-editor.cm-focused) { outline: none; }

/* 证据行高亮：普通行浅绿、当前查看行更深 */
.code-viewer__editor :deep(.cm-line-highlight) {
  background: color-mix(in oklch, var(--accent) 13%, transparent);
}
.code-viewer__editor :deep(.cm-line-active) {
  background: color-mix(in oklch, var(--accent) 24%, transparent);
  box-shadow: inset 2px 0 0 var(--accent);
}

.code-viewer__fallback { min-height: 240px; }
.code-viewer__fallback-pre {
  margin: 0;
  padding: 14px;
  color: oklch(0.84 0.01 155);
  font-family: var(--font-mono);
  font-size: var(--text-base);
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.code-viewer__toast { margin: 8px 0 0; font-size: var(--text-xs); color: var(--success); }
</style>
