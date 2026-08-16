<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import { sanitizeHtml } from '../../utils/sanitize.js'

const props = defineProps({
  cell: { type: Object, required: true },
})

const rendered = computed(() => {
  const src = props.cell.source || props.cell.rendered_html || ''
  // 如果是 HTML（旧版 rendered_html），直接清洗
  if (props.cell.rendered_html && !props.cell.source) {
    return sanitizeHtml(props.cell.rendered_html)
  }
  // 新版：raw markdown → marked → sanitize
  try {
    const html = marked.parse(src, { async: false })
    return sanitizeHtml(typeof html === 'string' ? html : '')
  } catch {
    return sanitizeHtml(src)
  }
})
</script>

<template>
  <div class="markdown-cell">
    <div class="cell-indicator">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 4h8M4 8h6M4 12h4"/>
      </svg>
      <span class="cell-label">讲解</span>
    </div>
    <div class="cell-body" v-html="rendered"></div>
  </div>
</template>

<style scoped>
.markdown-cell {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  margin-bottom: var(--space-4);
}

.cell-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: var(--space-3);
  color: var(--accent);
  font-size: var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.cell-body {
  line-height: 1.8;
  color: var(--fg);
  font-size: var(--text-sm);
}

.cell-body :deep(h1) {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--fg);
  margin: 24px 0 12px;
  letter-spacing: -0.01em;
}

.cell-body :deep(h2) {
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--fg);
  margin: 20px 0 10px;
  padding-top: var(--space-4);
  border-top: 1px solid var(--border);
  letter-spacing: -0.01em;
}

.cell-body :deep(h3) {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--fg);
  margin: 16px 0 8px;
}

.cell-body :deep(p) { margin: 8px 0; }

.cell-body :deep(a) {
  color: var(--accent);
  text-decoration: none;
}

.cell-body :deep(a:hover) {
  text-decoration: underline;
}

.cell-body :deep(code:not(pre code)) {
  font-family: var(--font-mono);
  font-size: 0.85em;
  background: var(--surface-subtle);
  color: var(--accent);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
}

.cell-body :deep(pre) {
  background: var(--surface);
  color: var(--fg);
  padding: var(--space-4);
  border-radius: var(--radius-md);
  overflow-x: auto;
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  box-shadow: var(--shadow-xs);
  margin: 12px 0;
  line-height: 1.7;
}

.cell-body :deep(pre code) {
  font-family: var(--font-mono);
  font-size: 13px;
  background: none;
  color: inherit;
  padding: 0;
}

.cell-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: var(--text-sm);
}

.cell-body :deep(th) {
  text-align: left;
  padding: 8px 12px;
  border-bottom: 2px solid var(--border);
  font-size: var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
  background: var(--surface-subtle);
}

.cell-body :deep(td) {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}

.cell-body :deep(blockquote) {
  background: var(--warning-bg);
  border-left: 3px solid var(--warning);
  padding: var(--space-3) var(--space-4);
  margin: 12px 0;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: var(--text-sm);
  color: var(--warning);
}

.cell-body :deep(img) {
  max-width: 100%;
  border-radius: var(--radius-md);
  margin: var(--space-3) 0;
}

.cell-body :deep(ul), .cell-body :deep(ol) {
  margin: 8px 0;
  padding-left: var(--space-6);
}

.cell-body :deep(li) { margin: 4px 0; }
</style>
