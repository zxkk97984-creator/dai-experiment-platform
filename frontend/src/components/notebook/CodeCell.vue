<script setup>
import {
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  watch,
} from 'vue'

const props = defineProps({
  cell: { type: Object, required: true },
  executionCount: { type: Number, default: null },
  disabled: { type: Boolean, default: false },
  isExecuting: { type: Boolean, default: false },
  /** 编辑只读：CodeMirror/textarea 不可编辑，不 emit update:source。运行仍可执行原源码 */
  readonly: { type: Boolean, default: false },
})

const emit = defineEmits(['execute', 'update:source'])

const editorEl = ref(null)
const cmView = shallowRef(null)
const cmLoaded = ref(false)
const code = ref(props.cell.source || '')
let syncingFromParent = false

// 同步代码回父组件（readonly 时不 emit）
watch(code, (val) => {
  if (!props.readonly && !syncingFromParent) {
    emit('update:source', props.cell.id, val)
  }
}, { flush: 'sync' })

// 外部 source 变化时同步到本地状态和 CodeMirror，但不把它误报为学生编辑。
watch(() => props.cell.source, (val) => {
  const nextSource = val || ''
  if (nextSource === code.value && cmView.value?.state.doc.toString() === nextSource) {
    return
  }

  syncingFromParent = true
  try {
    code.value = nextSource
    const view = cmView.value
    if (view && view.state.doc.toString() !== nextSource) {
      view.dispatch({
        changes: {
          from: 0,
          to: view.state.doc.length,
          insert: nextSource,
        },
      })
    }
  } finally {
    syncingFromParent = false
  }
})

// CodeMirror 初始化
async function initCodeMirror() {
  try {
    const [
      { EditorView, keymap, lineNumbers, highlightActiveLine },
      { EditorState },
      { python },
      { oneDark },
      { defaultKeymap, indentWithTab },
    ] = await Promise.all([
      import('@codemirror/view'),
      import('@codemirror/state'),
      import('@codemirror/lang-python'),
      import('@codemirror/theme-one-dark'),
      import('@codemirror/commands'),
    ])

    await nextTick()
    if (!editorEl.value) return

    const updateListener = EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        code.value = update.state.doc.toString()
      }
    })

    const state = EditorState.create({
      doc: code.value,
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        python(),
        oneDark,
        keymap.of([...defaultKeymap, indentWithTab]),
        updateListener,
        EditorView.editable.of(!props.readonly),
      ],
    })

    cmView.value = new EditorView({ state, parent: editorEl.value })
    cmLoaded.value = true
  } catch (e) {
    console.warn('CodeMirror load failed, using textarea fallback:', e.message)
    cmLoaded.value = false
  }
}

onMounted(initCodeMirror)

onBeforeUnmount(() => {
  if (cmView.value) {
    cmView.value.destroy()
    cmView.value = null
  }
})

function getOutputs() {
  if (!props.cell.outputs?.outputs) return []
  return props.cell.outputs.outputs
}

function outputType(output) {
  return output?.msg_type || output?.output_type || 'stream'
}

function outputText(output) {
  if (output.text) return output.text
  if (output.content?.text) return output.content.text
  if (output.content?.ename) {
    return `${output.content.ename}: ${output.content.evalue}\n${(output.content.traceback || []).join('\n')}`
  }
  return JSON.stringify(output)
}

function outputImageData(output) {
  const data = output?.data || output?.content?.data || {}
  return data['image/png'] || null
}

function handleRun() {
  if (props.disabled || props.isExecuting) return
  emit('execute', props.cell.id)
}

// readonly prop 变化时重建 editor
watch(() => props.readonly, () => {
  if (cmView.value) {
    cmView.value.destroy()
    cmView.value = null
    cmLoaded.value = false
    nextTick(() => initCodeMirror())
  }
})
</script>

<template>
  <div class="code-cell" :class="{ executing: isExecuting }">
    <!-- 标签 -->
    <div class="cell-indicator">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">
        <path d="M6 3v10l6-5z"/>
      </svg>
      <span class="cell-label">代码</span>
      <span v-if="executionCount !== null" class="exec-count">In [{{ executionCount }}]</span>
    </div>

    <!-- 编辑器 -->
    <div class="code-editor">
      <div ref="editorEl" class="editor-wrap">
        <!-- fallback: textarea（CodeMirror 加载失败时使用） -->
        <textarea
          v-if="!cmLoaded"
          v-model="code"
          class="code-textarea"
          :readonly="readonly"
          :aria-readonly="readonly"
          spellcheck="false"
          placeholder="在此输入 Python 代码..."
        ></textarea>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="code-toolbar">
      <button class="btn-run" @click="handleRun" :disabled="disabled || isExecuting">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="3,1 13,7 3,13"/>
        </svg>
        {{ isExecuting ? '运行中...' : '运行' }}
      </button>
      <span v-if="cell.outputs?.execution_time_ms" class="exec-time">
        {{ cell.outputs.execution_time_ms }}ms
      </span>
    </div>

    <!-- 输出区 -->
    <div v-if="getOutputs().length > 0" class="output-area">
      <div v-for="(output, i) in getOutputs()" :key="i" class="output-item">
        <pre
          v-if="outputType(output) === 'stream'"
          class="output-stream"
          :class="{ 'output-stderr': output.name === 'stderr' || output.content?.name === 'stderr' }"
        >{{ outputText(output) }}</pre>
        <pre v-else-if="outputType(output) === 'error'" class="output-error">{{ outputText(output) }}</pre>
        <img
          v-else-if="outputImageData(output)"
          :src="'data:image/png;base64,' + outputImageData(output)"
          class="output-image"
          alt="输出图片"
        />
        <pre v-else class="output-stream">{{ outputText(output) }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.code-cell {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
  overflow: hidden;
}

.code-cell.executing {
  border-left-color: var(--warning);
  box-shadow: 0 0 0 1px var(--warning);
}

.cell-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: var(--space-3) var(--space-5);
  background: var(--surface-raised);
  border-bottom: 1px solid var(--border);
  color: var(--accent);
  font-size: var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.exec-count {
  margin-left: auto;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-family: var(--font-mono);
}

.code-editor {
  border-bottom: 1px solid var(--border);
}

.editor-wrap {
  min-height: 48px;
}

/* ── CodeMirror 样式 ── */
.editor-wrap :deep(.cm-editor) {
  font-family: var(--font-mono);
  font-size: 13px;
}

.editor-wrap :deep(.cm-editor .cm-content) {
  padding: var(--space-3) var(--space-3) var(--space-3) 0;
}

.editor-wrap :deep(.cm-editor .cm-cursor) {
  border-left-color: #60A5FA !important;
  border-left-width: 2px;
}

.editor-wrap :deep(.cm-editor .cm-selectionBackground) {
  background: rgba(96, 165, 250, 0.3) !important;
}

.editor-wrap :deep(.cm-editor .cm-scroller) {
  cursor: text;
}

/* ── Textarea fallback ── */
.code-textarea {
  width: 100%;
  min-height: 80px;
  padding: var(--space-3) var(--space-4);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  background: #0F172A;
  color: #E2E8F0;
  caret-color: #60A5FA;
  border: none;
  outline: none;
  resize: vertical;
  tab-size: 4;
}

.code-textarea::placeholder {
  color: rgba(148, 163, 184, 0.4);
  font-style: italic;
}

.code-textarea:focus {
  outline: 2px solid #60A5FA;
  outline-offset: -2px;
  box-shadow: 0 0 8px rgba(96, 165, 250, 0.3);
}

.code-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-5);
  background: var(--surface-raised);
}

.btn-run {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: #fff;
  font-size: var(--text-xs);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast);
}

.btn-run:hover:not(:disabled) {
  background: var(--accent-dark);
  border-color: var(--accent-dark);
}

.btn-run:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.exec-time {
  margin-left: auto;
  font-size: var(--text-xs);
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

/* ── 输出区 ── */
.output-area {
  border-top: 1px solid var(--border);
  padding: var(--space-3) var(--space-5);
  background: #0F172A;
  max-height: 400px;
  overflow-y: auto;
}

.output-stream {
  margin: 0;
  padding: 2px 0;
  font-family: var(--font-mono);
  font-size: 12px;
  color: #E2E8F0;
  white-space: pre-wrap;
  word-break: break-word;
}

.output-stderr {
  color: #FCA5A5;
  background: rgba(239, 68, 68, 0.08);
  padding: 4px 8px;
  border-radius: 3px;
}

.output-error {
  margin: 0;
  padding: 8px 12px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: #FCA5A5;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-sm);
  white-space: pre-wrap;
}

.output-image {
  max-width: 100%;
  border-radius: var(--radius-sm);
  margin: 4px 0;
}
</style>
