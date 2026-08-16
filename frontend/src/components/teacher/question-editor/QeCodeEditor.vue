<script setup>
// QeCodeEditor：题目编辑页使用的深色 Python 代码编辑器（CodeMirror 6 + oneDark）。
// 能力：行号 / Python 语法高亮 / Tab 缩进 / 横向纵向滚动 / 右下角拖拽调高 / 全屏。
// 固定高度（默认 360px，不随代码行数增长），内容过长时编辑器内部滚动。
// 参考 CodeCell.vue 的动态加载与 v-model 同步方式；主题沿用 CodeViewer.vue 的 oneDark 深色。
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  /** 初始高度（px），用户可拖拽调整 */
  height: { type: Number, default: 360 },
  /** 全屏态（由父组件标题栏按钮控制） */
  fullscreen: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'update:fullscreen'])

const editorEl = ref(null)
const cmView = shallowRef(null)
const cmLoaded = ref(false)
const code = ref(props.modelValue || '')
// 拖拽调整后的实际高度（px）；拖动过程中不写回 props，避免与父组件互相干扰
const editHeight = ref(props.height)
const dragging = ref(false)
let syncingFromParent = false

// 同步代码回父组件（拖动高度时也同步，防止父组件快照回写）
watch(code, (val) => {
  if (!syncingFromParent) emit('update:modelValue', val)
}, { flush: 'sync' })

// 外部 modelValue 变化 → 同步到本地与 CodeMirror（不回发事件）
watch(() => props.modelValue, (val) => {
  const next = val || ''
  if (next === code.value && cmView.value?.state.doc.toString() === next) return
  syncingFromParent = true
  try {
    code.value = next
    const view = cmView.value
    if (view && view.state.doc.toString() !== next) {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: next } })
    }
  } finally {
    syncingFromParent = false
  }
})

// 父组件改初始高度（如重置表单）时跟随
watch(() => props.height, (h) => {
  if (!dragging.value) editHeight.value = h
})

// ── CodeMirror 初始化（动态加载，失败降级 textarea） ────────────────
async function initCodeMirror() {
  try {
    const [
      { EditorView, drawSelection, keymap, lineNumbers, highlightActiveLine, placeholder: cmPlaceholder },
      { EditorState },
      { python },
      { defaultKeymap, indentWithTab },
      { oneDark },
    ] = await Promise.all([
      import('@codemirror/view'),
      import('@codemirror/state'),
      import('@codemirror/lang-python'),
      import('@codemirror/commands'),
      import('@codemirror/theme-one-dark'),
    ])

    await nextTick()
    if (!editorEl.value) return

    const updateListener = EditorView.updateListener.of((update) => {
      if (update.docChanged) code.value = update.state.doc.toString()
    })

    const state = EditorState.create({
      doc: code.value,
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        drawSelection(),
        python(),
        oneDark,
        cmPlaceholder(props.placeholder || ''),
        keymap.of([...defaultKeymap, indentWithTab]),
        updateListener,
      ],
    })

    cmView.value = new EditorView({ state, parent: editorEl.value })
    cmLoaded.value = true
  } catch (e) {
    console.warn('QeCodeEditor CodeMirror load failed, using textarea fallback:', e?.message || e)
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

// ── 高度拖拽：右下角手柄 → 调整编辑区高度 ─────────────────────────
function startDrag(e) {
  e.preventDefault()
  dragging.value = true
  const startY = e.clientY
  const startH = editHeight.value
  const onMove = (ev) => {
    const next = Math.max(140, startH + (ev.clientY - startY))
    editHeight.value = Math.min(next, 1200)
    if (cmView.value) cmView.value.requestMeasure()
  }
  const onUp = () => {
    dragging.value = false
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

// ── 全屏切换后让 CodeMirror 重新测量 ───────────────────────────────
watch(() => props.fullscreen, () => {
  nextTick().then(() => {
    if (cmView.value) cmView.value.requestMeasure()
  })
})
</script>

<template>
  <div
    class="qe-code"
    :class="{ 'qe-code--fullscreen': fullscreen, 'qe-code--dragging': dragging }"
    :style="{ height: fullscreen ? '100%' : editHeight + 'px' }"
  >
    <div ref="editorEl" class="qe-code__wrap">
      <!-- fallback: textarea（CodeMirror 加载失败时使用，样式保持深色语义） -->
      <textarea
        v-if="!cmLoaded"
        v-model="code"
        class="qe-code__fallback"
        :placeholder="placeholder"
        spellcheck="false"
      ></textarea>
    </div>
    <button
      v-if="!fullscreen"
      type="button"
      class="qe-code__resize"
      aria-label="拖动调整编辑器高度"
      title="拖动调整高度"
      @mousedown="startDrag"
    ></button>
  </div>
</template>

<style scoped>
/* 深色代码编辑器（oneDark 主题由扩展层管理，这里只负责布局与容器） */
.qe-code {
  position: relative;
  min-width: 0;
  border: 1px solid oklch(0.32 0.02 155);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: oklch(0.225 0.018 155);
  transition: height 80ms ease-out;
}

.qe-code--dragging {
  transition: none;
  user-select: none;
}

.qe-code__wrap,
.qe-code__wrap :deep(.cm-editor),
.qe-code__wrap :deep(.cm-scroller) {
  height: 100%;
}

.qe-code__wrap :deep(.cm-editor) {
  font-family: var(--font-mono);
  font-size: 13px;
}

.qe-code__wrap :deep(.cm-editor .cm-content) {
  padding: 10px 0;
}

.qe-code__wrap :deep(.cm-editor.cm-focused) {
  outline: none;
}

/* 全屏态：盖住整个视口（相对左侧导航内容区右侧），深色底 + 内滚 */
.qe-code--fullscreen {
  position: fixed;
  inset: 64px 0 0 var(--sidebar-width);
  z-index: 900;
  height: calc(100vh - 64px) !important;
  border-radius: 0;
  border: none;
}

.qe-code--fullscreen :deep(.cm-scroller) {
  height: 100%;
}

/* 侧栏折叠（≤1199px）时全屏态跟随收缩 */
@media (max-width: 1199px) {
  .qe-code--fullscreen {
    left: var(--sidebar-collapsed-width);
  }
}

/* 右下角拖拽手柄 */
.qe-code__resize {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 18px;
  height: 18px;
  border: none;
  background: transparent;
  cursor: ns-resize;
  z-index: 5;
}

.qe-code__resize::after {
  content: '';
  position: absolute;
  right: 4px;
  bottom: 4px;
  width: 8px;
  height: 8px;
  border-right: 2px solid var(--muted);
  border-bottom: 2px solid var(--muted);
  border-radius: 0 0 2px 0;
  opacity: 0.7;
  transition: opacity 120ms ease-out;
}

.qe-code:hover .qe-code__resize::after,
.qe-code__resize:hover::after {
  opacity: 1;
}

/* textarea fallback（与深色编辑器一致） */
.qe-code__fallback {
  width: 100%;
  height: 100%;
  padding: 12px;
  border: none;
  outline: none;
  resize: none;
  background: oklch(0.225 0.018 155);
  color: var(--border);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  tab-size: 4;
}

.qe-code__fallback::placeholder {
  color: var(--muted);
  font-style: italic;
}
</style>
