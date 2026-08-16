<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'
import { sanitizeHtml } from '../../utils/sanitize.js'
import AppIcon from '../ui/AppIcon.vue'

const props = defineProps({
  cell: { type: Object, required: true },
})

const copied = ref(false)
const isMarkdown = computed(() => props.cell.type === 'markdown')
const lines = computed(() => String(props.cell.source || '').split('\n'))
const outputs = computed(() => props.cell.outputs?.outputs || [])
const renderedMarkdown = computed(() => {
  try {
    const html = marked.parse(props.cell.source || '', { async: false })
    return sanitizeHtml(typeof html === 'string' ? html : '')
  } catch {
    return sanitizeHtml(props.cell.source || '')
  }
})

function outputType(output) {
  return output?.msg_type || output?.output_type || 'stream'
}

function outputText(output) {
  if (typeof output?.text === 'string') return output.text
  if (typeof output?.content?.text === 'string') return output.content.text
  if (output?.content?.ename) {
    return `${output.content.ename}: ${output.content.evalue || ''}\n${(output.content.traceback || []).join('\n')}`
  }
  const data = output?.data || output?.content?.data
  if (typeof data === 'string') return data
  if (data?.['text/plain']) return data['text/plain']
  return JSON.stringify(output, null, 2)
}

function outputImageData(output) {
  const data = output?.data || output?.content?.data || {}
  return data['image/png'] || null
}

async function copySource() {
  await navigator.clipboard.writeText(props.cell.source || '')
  copied.value = true
  window.setTimeout(() => { copied.value = false }, 1500)
}
</script>

<template>
  <article class="snapshot-cell" :class="{ markdown: isMarkdown }">
    <header class="cell-head">
      <span class="cell-kind">
        <AppIcon :name="isMarkdown ? 'assignment' : 'code'" :size="15" />
        {{ isMarkdown ? 'Markdown' : 'Code' }}
      </span>
      <span class="cell-order">#{{ cell.order }}</span>
      <button
        v-if="!isMarkdown && cell.source"
        type="button"
        class="copy-button"
        :aria-label="copied ? '已复制代码' : '复制代码'"
        @click="copySource"
      >
        <AppIcon :name="copied ? 'check' : 'copy'" :size="15" />
        {{ copied ? '已复制' : '复制' }}
      </button>
    </header>

    <div v-if="isMarkdown" class="markdown-body" v-html="renderedMarkdown"></div>
    <div v-else class="code-body">
      <div class="line-numbers" aria-hidden="true">
        <span v-for="(_, index) in lines" :key="index">{{ index + 1 }}</span>
      </div>
      <pre><code>{{ cell.source || '(空)' }}</code></pre>
    </div>

    <section v-if="outputs.length" class="output-area">
      <header>
        <span class="output-label"><AppIcon name="code" :size="15" /> Output</span>
        <span v-if="cell.outputs?.execution_count != null">执行计数 {{ cell.outputs.execution_count }}</span>
      </header>
      <div v-for="(output, index) in outputs" :key="index" class="output-item">
        <img
          v-if="outputImageData(output)"
          :src="`data:image/png;base64,${outputImageData(output)}`"
          alt="程序输出图片"
        />
        <pre v-else :class="{ error: outputType(output) === 'error' }">{{ outputText(output) }}</pre>
      </div>
    </section>
  </article>
</template>

<style scoped>
.snapshot-cell { overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); }
.cell-head {
  min-height: 42px; display: flex; align-items: center; gap: 10px; padding: 8px 12px;
  border-bottom: 1px solid var(--border); background: var(--surface-subtle);
}
.cell-kind { display: inline-flex; align-items: center; gap: 6px; color: var(--accent); font-size: 12px; font-weight: 600; }
.cell-order { color: var(--faint); font-size: 12px; }
.copy-button {
  margin-left: auto; padding: 4px 8px; display: inline-flex; align-items: center; gap: 5px;
  border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface);
  color: var(--muted); font-size: 11px; cursor: pointer;
}
.copy-button:hover { border-color: var(--accent-soft); color: var(--accent); background: var(--accent-soft); }
.code-body { display: grid; grid-template-columns: 42px minmax(0, 1fr); min-height: 70px; overflow-x: auto; }
.line-numbers {
  padding: 14px 10px; display: flex; flex-direction: column; align-items: flex-end;
  border-right: 1px solid var(--border); background: var(--surface-subtle); color: var(--faint);
  font-family: var(--font-mono); font-size: 12px; line-height: 1.7; user-select: none;
}
.code-body pre { min-width: max-content; margin: 0; padding: 14px 16px; color: var(--fg); font-family: var(--font-mono); font-size: 12.5px; line-height: 1.7; white-space: pre; }
.code-body code { padding: 0; border: 0; background: none; color: inherit; font: inherit; }
.markdown-body { padding: 16px 18px; color: var(--fg); font-size: 13px; line-height: 1.75; }
.markdown-body :deep(:first-child) { margin-top: 0; }
.markdown-body :deep(:last-child) { margin-bottom: 0; }
.markdown-body :deep(h1) { margin: 0 0 10px; font-size: 21px; }
.markdown-body :deep(h2) { margin: 14px 0 8px; font-size: 17px; }
.markdown-body :deep(p) { margin: 8px 0; }
.markdown-body :deep(code) { font-size: 12px; }
.markdown-body :deep(pre) { overflow-x: auto; padding: 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface-subtle); }
.output-area { border-top: 1px solid var(--border); background: var(--surface-subtle); }
.output-area > header { display: flex; justify-content: space-between; padding: 9px 12px; color: var(--faint); font-size: 11px; }
.output-label { display: inline-flex; align-items: center; gap: 6px; color: var(--accent); font-weight: 600; }
.output-item { padding: 0 12px 12px; }
.output-item pre { margin: 0; padding: 10px 12px; border-radius: var(--radius-sm); background: var(--surface-subtle); color: var(--fg); font-family: var(--font-mono); font-size: 12px; white-space: pre-wrap; word-break: break-word; }
.output-item pre.error { color: var(--danger); background: var(--danger-bg); }
.output-item img { max-width: 100%; border-radius: var(--radius-sm); }
</style>
