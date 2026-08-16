<script setup>
// QeMarkdownEditor：题目描述 Markdown 编辑器（编辑 / 预览 切换）。
// 工具栏支持加粗/斜体/标题/列表/代码块/链接/表格，操作当前选区。
// 编辑区固定高度（默认 180px），内容过长内部滚动，不撑高页面。
// 预览使用项目已有 marked + sanitizeHtml（与讲义编辑页同款渲染管线）。
import { computed, ref } from 'vue'
import { marked } from 'marked'
import { sanitizeHtml } from '../../../utils/sanitize.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
  /** 编辑区高度（px） */
  height: { type: Number, default: 180 },
})

const emit = defineEmits(['update:modelValue'])

const mode = ref('edit') // edit | preview
const taEl = ref(null)

// ── 预览：marked → sanitize（与 ChapterManageView / 讲义编辑页同款） ─
const previewHtml = computed(() => {
  const raw = marked.parse(props.modelValue || '', { async: false })
  return sanitizeHtml(typeof raw === 'string' ? raw : '')
})

// ── 工具栏：在选区前后插入 markdown 语法 ────────────────────────────
function insertWrapper(prefix, suffix, placeholder) {
  const ta = taEl.value
  if (!ta) return
  const start = ta.selectionStart ?? props.modelValue.length
  const end = ta.selectionEnd ?? props.modelValue.length
  const selected = props.modelValue.slice(start, end)
  const body = selected || placeholder || ''
  const next = props.modelValue.slice(0, start) + prefix + body + suffix + props.modelValue.slice(end)
  emit('update:modelValue', next)
  // 光标移到插入内容之后（若 DOM 已更新则尝试定位）
  const caret = start + prefix.length + body.length
  requestAnimationFrame(() => {
    if (ta) {
      ta.focus()
      ta.setSelectionRange(caret, caret)
    }
  })
}

function insertLine(prefix, placeholder) {
  const ta = taEl.value
  if (!ta) return
  const start = ta.selectionStart ?? props.modelValue.length
  const before = props.modelValue.slice(0, start)
  const after = props.modelValue.slice(start)
  const needNewline = before.length > 0 && !before.endsWith('\n')
  const next = before + (needNewline ? '\n' : '') + prefix + (placeholder || '') + (after.startsWith('\n') ? after : '\n' + after)
  emit('update:modelValue', next)
  const caret = (needNewline ? 1 : 0) + before.length + prefix.length + (placeholder || '').length
  requestAnimationFrame(() => {
    if (ta) {
      ta.focus()
      ta.setSelectionRange(caret, caret)
    }
  })
}

// 工具栏按钮定义：{ label, icon(emoji/文本), action }
const tools = [
  { key: 'bold', label: '加粗', icon: 'B', title: '加粗', action: () => insertWrapper('**', '**', '加粗文本') },
  { key: 'italic', label: '斜体', icon: 'I', title: '斜体', action: () => insertWrapper('*', '*', '斜体文本') },
  { key: 'heading', label: '标题', icon: 'H', title: '标题', action: () => insertLine('## ', '标题') },
  { key: 'ul', label: '无序列表', icon: '•', title: '无序列表', action: () => insertLine('- ', '列表项') },
  { key: 'ol', label: '有序列表', icon: '1.', title: '有序列表', action: () => insertLine('1. ', '列表项') },
  {
    key: 'code', label: '代码块', icon: '</>', title: '代码块',
    action: () => insertWrapper('```python\n', '\n```', 'print("hello")'),
  },
  {
    key: 'link', label: '链接', icon: '🔗', title: '插入链接',
    action: () => insertWrapper('[', '](https://)', '链接文字'),
  },
  {
    key: 'table', label: '表格', icon: '≡', title: '插入表格',
    action: () => insertLine('| 参数 | 说明 |\n| --- | --- |\n|  |  |', ''),
  },
]
</script>

<template>
  <div class="qe-md">
    <!-- 工具栏：左侧格式按钮，右侧 编辑 | 预览 切换 -->
    <div class="qe-md__toolbar">
      <div class="qe-md__tools">
        <button
          v-for="t in tools"
          :key="t.key"
          type="button"
          class="qe-md__tool"
          :title="t.title"
          @mousedown.prevent
          @click="mode === 'edit' ? t.action() : null"
        >{{ t.icon }}</button>
      </div>
      <div class="qe-md__tabs" role="tablist">
        <button
          type="button"
          class="qe-md__tab"
          :class="{ active: mode === 'edit' }"
          role="tab"
          :aria-selected="mode === 'edit'"
          @click="mode = 'edit'"
        >编辑</button>
        <button
          type="button"
          class="qe-md__tab"
          :class="{ active: mode === 'preview' }"
          role="tab"
          :aria-selected="mode === 'preview'"
          @click="mode = 'preview'"
        >预览</button>
      </div>
    </div>

    <!-- 编辑区 / 预览区：固定高度，内部滚动 -->
    <div class="qe-md__body" :style="{ height: height + 'px' }">
      <textarea
        v-show="mode === 'edit'"
        ref="taEl"
        class="qe-md__textarea"
        :value="modelValue"
        spellcheck="false"
        placeholder="支持 Markdown 语法描述题目，如公式、示例说明、数据范围…"
        @input="emit('update:modelValue', $event.target.value)"
      ></textarea>
      <div v-show="mode === 'preview'" class="qe-md__preview markdown-body" v-html="previewHtml"></div>
    </div>
  </div>
</template>

<style scoped>
.qe-md {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--surface);
}

.qe-md__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px;
  background: var(--surface-subtle);
  border-bottom: 1px solid var(--border);
}

.qe-md__tools {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-wrap: wrap;
}

.qe-md__tool {
  min-width: 28px;
  height: 26px;
  padding: 0 6px;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--duration-fast), color var(--duration-fast);
}

.qe-md__tool:hover {
  background: var(--surface);
  color: var(--accent);
  border-color: var(--border);
}

.qe-md__tool:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.qe-md__tabs {
  display: flex;
  gap: 2px;
}

.qe-md__tab {
  padding: 3px 12px;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
}

.qe-md__tab:hover {
  color: var(--fg);
}

.qe-md__tab.active {
  background: var(--surface);
  border-color: var(--border);
  color: var(--accent);
  font-weight: 600;
}

/* 编辑 / 预览共用固定高度容器：内容超出内部滚动 */
.qe-md__body {
  overflow-y: auto;
}

.qe-md__textarea {
  width: 100%;
  height: 100%;
  padding: 12px 14px;
  border: none;
  outline: none;
  resize: none;
  background: var(--surface);
  color: var(--fg);
  font-family: inherit;
  font-size: var(--text-sm);
  line-height: 1.7;
}

.qe-md__textarea::placeholder {
  color: var(--faint);
  font-style: italic;
}

.qe-md__textarea:focus {
  box-shadow: inset 0 0 0 2px var(--accent);
}

.qe-md__preview {
  height: 100%;
  padding: 12px 14px;
  font-size: var(--text-sm);
  line-height: 1.7;
  overflow-y: auto;
  color: var(--fg);
}

/* 预览内嵌 Markdown 基础样式（作用域内，避免污染全局） */
.qe-md__preview :deep(p) { margin: 0 0 10px; }
.qe-md__preview :deep(h1), .qe-md__preview :deep(h2), .qe-md__preview :deep(h3) { margin: 14px 0 8px; font-weight: 600; }
.qe-md__preview :deep(pre) {
  background: var(--fg); color: var(--border); padding: 10px 12px; border-radius: var(--radius-md);
  overflow-x: auto; font-family: var(--font-mono); font-size: 12px;
}
.qe-md__preview :deep(code) { font-family: var(--font-mono); font-size: 12px; }
.qe-md__preview :deep(pre code) { background: transparent; padding: 0; }
.qe-md__preview :deep(code:not(pre code)) { background: var(--surface-subtle); padding: 1px 5px; border-radius: var(--radius-sm); }
.qe-md__preview :deep(table) { border-collapse: collapse; margin: 8px 0; }
.qe-md__preview :deep(th), .qe-md__preview :deep(td) { border: 1px solid var(--border); padding: 5px 10px; }
.qe-md__preview :deep(blockquote) { border-left: 3px solid var(--border-strong); margin: 8px 0; padding: 2px 12px; color: var(--muted); }
.qe-md__preview :deep(a) { color: var(--accent); }
.qe-md__preview :deep(img) { max-width: 100%; }
</style>
