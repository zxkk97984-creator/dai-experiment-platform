<script setup>
import { computed, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import CodeCell from './CodeCell.vue'
import MarkdownCell from './MarkdownCell.vue'
import { useStudioStore } from '../../stores/studio.js'
import { useAppStore } from '../../stores/app.js'

const props = defineProps({ templateId: { type: [Number, String], required: true } })
const store = useStudioStore()
const app = useAppStore()
const loading = ref(true)
const history = ref([])
const showHistory = ref(false)
const editingMarkdownCell = ref(null)
const markdownEditSource = ref('')
const leaving = ref(false)

const visibleCells = computed(() => store.studentPreview ? store.sortedCells.filter(c => !c.source_hidden) : store.sortedCells)

onBeforeRouteLeave(async (_to, _from) => {
  if (leaving.value) return true
  if (store.dirty && !store.conflict) {
    if (!window.confirm('有未保存的修改，确定离开吗？')) return false
  }
  store.destroy()
  return true
})

async function init() {
  loading.value = true
  try { await store.open(props.templateId) }
  catch { app.showToast('加载模板失败', 'error') }
  finally { loading.value = false }
}
init()

async function handleSave() { await store.saveDraft() }
async function handlePublish() { await store.publish() }

function onFileChange(e) {
  const f = e.target.files[0]
  if (!f) return
  store.importExisting(f).then(() => app.showToast('导入成功', 'success')).catch(e => app.showToast(e.response?.data?.detail?.message || '导入失败', 'error'))
}

async function loadHistory() {
  try {
    const { studioAPI } = await import('../../api/studio.js')
    const res = await studioAPI.getVersions(props.templateId)
    history.value = res.data || []
  } catch { }
  showHistory.value = true
}

function handleRun(cellId) { store.previewRun(cellId) }
function handleUpdateSource(cellId, source) { store.updateCellSource(cellId, source) }
function handleMarkdownEdit(cellId) {
  if (editingMarkdownCell.value === cellId) {
    const cell = store.cells.find(c => c.id === cellId)
    if (cell) cell.source = markdownEditSource.value
    editingMarkdownCell.value = null
  } else {
    const cell = store.cells.find(c => c.id === cellId)
    markdownEditSource.value = cell?.source || ''
    editingMarkdownCell.value = cellId
  }
}
</script>
<template>
  <div v-if="loading" class="studio-loading">
    <div class="skeleton-bar" v-for="i in 3" :key="i" :style="{ width: (60 + i * 15) + '%' }"></div>
  </div>
  <div v-else class="studio-editor">
    <div class="studio-toolbar">
      <div class="toolbar-left">
        <h2 class="studio-name">{{ store.name || '未命名模板' }}</h2>
        <span class="revision-badge">rev {{ store.draftRevision }}</span>
      </div>
      <div class="toolbar-right">
        <span class="save-state" :class="{ dirty: store.dirty, conflict: store.conflict }">{{ store.conflict ? '冲突' : store.dirty ? '未保存' : store.saving ? '保存中…' : '已保存' }}</span>
        <button class="tb-btn" @click="handleSave" :disabled="store.saving || store.conflict">保存</button>
        <button class="tb-btn tb-btn-accent" @click="handlePublish" :disabled="store.saving">发布</button>
        <label class="tb-btn">导入<input type="file" accept=".ipynb,.zip" class="hidden-input" @change="onFileChange" /></label>
        <button class="tb-btn" @click="store.exportDraft()">导出</button>
        <button class="tb-btn" @click="loadHistory">历史</button>
        <button class="tb-btn" :class="{ active: store.studentPreview }" @click="store.studentPreview = !store.studentPreview">预览</button>
      </div>
    </div>
    <div v-if="store.conflict" class="conflict-banner">
      <span>{{ store.conflictMessage }}</span>
      <button class="conflict-reload" @click="init">刷新</button>
    </div>
    <p v-if="store.description" class="studio-desc">{{ store.description }}</p>
    <div v-if="store.studentPreview" class="preview-notice">学生视角 — 隐藏 Cell 不显示，不可编辑</div>
    <div v-for="cell in visibleCells" :key="cell.id" class="cell-editor-wrapper">
      <div v-if="!store.studentPreview" class="cell-toolbar">
        <span class="cell-type-badge" :class="cell.type">{{ cell.type === 'code' ? 'Python' : 'MD' }}</span>
        <div class="cell-actions">
          <button v-if="cell.type === 'code'" class="cell-action-btn" :class="{ on: cell.student_editable !== false }" @click="store.setCellEditable(cell.id, cell.student_editable === false)">编辑</button>
          <button v-if="cell.type === 'code'" class="cell-action-btn" :class="{ on: cell.source_hidden }" @click="store.setCellHidden(cell.id, !cell.source_hidden)">隐藏</button>
          <button class="cell-action-btn" @click="store.addCell('markdown', cell.order)">+讲解</button>
          <button class="cell-action-btn" @click="store.addCell('code', cell.order)">+代码</button>
          <button class="cell-action-btn" @click="store.duplicateCell(cell.id)">复制</button>
          <button class="cell-action-btn" @click="store.moveCell(cell.id, 'up')">上移</button>
          <button class="cell-action-btn" @click="store.moveCell(cell.id, 'down')">下移</button>
          <button class="cell-action-btn cell-action-del" @click="store.deleteCell(cell.id)">删除</button>
        </div>
      </div>
      <template v-if="cell.type === 'markdown'">
        <div v-if="editingMarkdownCell === cell.id && !store.studentPreview" class="md-editor-wrap">
          <textarea v-model="markdownEditSource" class="md-textarea" placeholder="Markdown 内容…" rows="6"></textarea>
          <div class="md-editor-bar"><button class="tb-btn tb-btn-sm" @click="handleMarkdownEdit(cell.id)">完成</button></div>
        </div>
        <div v-else class="md-show-wrap" @dblclick="!store.studentPreview && handleMarkdownEdit(cell.id)">
          <MarkdownCell :cell="{ ...cell, source: cell.source || '', rendered_html: '' }" />
          <button v-if="!store.studentPreview" class="md-edit-hint" @click="handleMarkdownEdit(cell.id)">双击编辑</button>
        </div>
      </template>
      <CodeCell
        v-else
        :cell="{ id: cell.id, type: 'code', source: cell.source, outputs: cell._previewOutputs || null, student_editable: cell.student_editable !== false }"
        :execution-count="cell._previewOutputs?.execution_count ?? null"
        :disabled="cell.source_hidden || (store.runningCellId !== null && store.runningCellId !== cell.id)"
        :readonly="store.studentPreview && cell.student_editable === false"
        :is-executing="store.runningCellId === cell.id"
        @execute="handleRun"
        @update:source="handleUpdateSource"
      />
    </div>
    <div v-if="visibleCells.length === 0 && !loading" class="studio-empty">
      <p>暂无 Cell</p>
      <div class="empty-actions">
        <button class="tb-btn" @click="store.addCell('markdown', -1)">+ 添加讲解</button>
        <button class="tb-btn" @click="store.addCell('code', -1)">+ 添加代码</button>
      </div>
    </div>
    <div v-if="showHistory" class="modal-overlay" @click.self="showHistory = false">
      <div class="modal-content history-modal">
        <div class="modal-header"><h3>版本历史</h3><button class="modal-close" @click="showHistory = false">✕</button></div>
        <div class="modal-body">
          <p v-if="history.length === 0" class="text-secondary">暂无已发布版本</p>
          <div v-for="v in history" :key="v.id" class="history-item">
            <span class="version-num">v{{ v.version_number }}</span>
            <span class="version-sha">{{ v.sha256.slice(0, 12) }}</span>
            <span class="version-date">{{ new Date(v.published_at).toLocaleString() }}</span>
            <button class="tb-btn tb-btn-sm" @click="store.exportVersion(v.id)">导出</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<style scoped>
.studio-loading { padding: var(--space-6); }
.skeleton-bar { height: 16px; margin-bottom: var(--space-3); background: var(--border); border-radius: var(--radius-sm); animation: pulse 1.2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }
.studio-editor { max-width: 960px; margin: 0 auto; }
.studio-toolbar { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) 0; margin-bottom: var(--space-3); border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.toolbar-left { display: flex; align-items: center; gap: var(--space-2); }
.studio-name { font-size: var(--text-lg); font-weight: 600; margin: 0; }
.revision-badge { font-size: var(--text-xs); color: var(--text-secondary); background: var(--surface-raised); padding: 2px 6px; border-radius: var(--radius-sm); }
.toolbar-right { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.save-state { font-size: var(--text-xs); color: var(--text-secondary); white-space: nowrap; }
.save-state.dirty { color: var(--warning); }
.save-state.conflict { color: var(--error); }
.tb-btn { display: inline-flex; align-items: center; gap: 4px; padding: 5px 10px; font-size: var(--text-xs); font-weight: 500; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface); color: var(--text); cursor: pointer; transition: all var(--duration-fast); white-space: nowrap; position: relative; }
.tb-btn:hover { border-color: var(--border-strong); background: var(--surface-raised); }
.tb-btn:disabled { opacity: .5; cursor: not-allowed; }
.tb-btn.active { border-color: var(--primary); color: var(--primary); }
.tb-btn-accent { background: var(--accent); color: #fff; border-color: var(--accent); }
.tb-btn-accent:hover { background: var(--accent-dark); }
.tb-btn-sm { padding: 3px 8px; font-size: 11px; }
.hidden-input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.conflict-banner { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-3) var(--space-4); margin-bottom: var(--space-3); background: rgba(239, 68, 68, .08); border: 1px solid rgba(239, 68, 68, .3); border-radius: var(--radius-md); color: var(--error); font-size: var(--text-sm); }
.conflict-reload { margin-left: auto; background: var(--error); color: #fff; border: none; padding: 4px 12px; border-radius: var(--radius-sm); cursor: pointer; font-size: var(--text-xs); }
.studio-desc { font-size: var(--text-sm); color: var(--text-secondary); margin-bottom: var(--space-3); }
.preview-notice { padding: var(--space-2) var(--space-4); margin-bottom: var(--space-3); background: var(--warning-light); border-left: 3px solid var(--warning); border-radius: 0 var(--radius-sm) var(--radius-sm) 0; font-size: var(--text-xs); color: #7C5E0A; }
.cell-editor-wrapper { margin-bottom: var(--space-3); }
.cell-toolbar { display: flex; align-items: center; gap: 4px; padding: 4px 8px; background: var(--surface-raised); border: 1px solid var(--border); border-bottom: none; border-radius: var(--radius-sm) var(--radius-sm) 0 0; }
.cell-type-badge { font-size: 10px; font-weight: 600; text-transform: uppercase; padding: 1px 6px; border-radius: 3px; }
.cell-type-badge.code { background: rgba(249, 115, 22, .1); color: var(--accent); }
.cell-type-badge.markdown { background: rgba(59, 130, 246, .1); color: var(--primary); }
.cell-actions { margin-left: auto; display: flex; gap: 2px; }
.cell-action-btn { background: none; border: 1px solid transparent; border-radius: var(--radius-sm); padding: 1px 5px; font-size: 12px; cursor: pointer; color: var(--text-secondary); }
.cell-action-btn:hover { border-color: var(--border); background: var(--surface); }
.cell-action-btn.on { color: var(--primary); }
.cell-action-del:hover { color: var(--error); border-color: rgba(239, 68, 68, .3); }
.md-editor-wrap { border: 1px solid var(--border); border-top: none; }
.md-textarea { width: 100%; padding: var(--space-3) var(--space-4); border: none; outline: none; font-family: var(--font-mono); font-size: 13px; line-height: 1.6; resize: vertical; background: var(--surface); color: var(--text); }
.md-editor-bar { padding: var(--space-2) var(--space-3); border-top: 1px solid var(--border); background: var(--surface-raised); }
.md-show-wrap { position: relative; cursor: default; }
.md-edit-hint { position: absolute; top: 4px; right: 8px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 1px 6px; font-size: 10px; color: var(--text-tertiary); cursor: pointer; }
.studio-empty { text-align: center; padding: var(--space-12); color: var(--text-secondary); }
.empty-actions { display: flex; gap: var(--space-2); justify-content: center; margin-top: var(--space-3); }
.modal-overlay { position: fixed; inset: 0; z-index: 100; background: rgba(0,0,0,.3); display: flex; align-items: center; justify-content: center; }
.modal-content { background: var(--surface); border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); max-width: 560px; width: 90vw; max-height: 80vh; overflow-y: auto; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: var(--space-4); border-bottom: 1px solid var(--border); }
.modal-header h3 { margin: 0; font-size: var(--text-md); }
.modal-close { background: none; border: none; cursor: pointer; font-size: 16px; color: var(--text-secondary); }
.modal-body { padding: var(--space-4); }
.history-item { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) 0; border-bottom: 1px solid var(--border); font-size: var(--text-sm); }
.history-item:last-child { border-bottom: none; }
.version-num { font-weight: 600; min-width: 36px; }
.version-sha { font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary); }
.version-date { color: var(--text-secondary); flex: 1; }
</style>
