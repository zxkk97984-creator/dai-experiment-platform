import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { studioAPI } from '../api/studio.js'
import { useAppStore } from './app.js'

export const useStudioStore = defineStore('studio', () => {
  const app = useAppStore()

  const templateId = ref(null)
  const name = ref('')
  const description = ref('')
  const status = ref('draft')
  const draftRevision = ref(1)
  const draftRevisionSaved = ref(1)
  const cells = ref([])
  const currentVersionId = ref(null)
  const lessonId = ref(null)
  const moduleId = ref(null)
  const ownerId = ref(null)

  const dirty = ref(false)
  const saving = ref(false)
  const saved = ref(false)
  const conflict = ref(false)
  const conflictMessage = ref('')
  const error = ref(null)
  const studentPreview = ref(false)
  const executingCellId = ref(null)
  const runningCellId = ref(null)

  const sortedCells = computed(() => {
    return [...cells.value].sort((a, b) => a.order - b.order)
  })

  function _genId() {
    return 'cell-' + crypto.randomUUID().slice(0, 8)
  }

  // 加载
  async function open(id) {
    templateId.value = id
    const res = await studioAPI.getTemplate(id)
    const d = res.data
    name.value = d.name
    description.value = d.description || ''
    status.value = d.status
    draftRevision.value = d.draft_revision
    draftRevisionSaved.value = d.draft_revision
    cells.value = (d.draft_cells || []).map(c => ({ ...c }))
    currentVersionId.value = d.current_version_id
    lessonId.value = d.lesson_id
    moduleId.value = d.module_id
    ownerId.value = d.owner_id
    dirty.value = false
    saved.value = true
    conflict.value = false
    error.value = null
    studentPreview.value = false
  }

  // 空白创建
  async function create(payload) {
    const res = await studioAPI.createTemplate(payload)
    await open(res.data.id)
    return res.data
  }

  // 导入创建
  async function importNew(name, desc, file, lessonIdVal, moduleIdVal) {
    const fd = new FormData()
    fd.append('name', name)
    if (desc) fd.append('description', desc)
    if (lessonIdVal) fd.append('lesson_id', String(lessonIdVal))
    if (moduleIdVal) fd.append('module_id', String(moduleIdVal))
    fd.append('file', file)
    const res = await studioAPI.importNew(fd)
    await open(res.data.id)
    return res.data
  }

  // 导入已有模板
  async function importExisting(file) {
    const fd = new FormData()
    fd.append('draft_revision', String(draftRevision.value))
    fd.append('file', file)
    const res = await studioAPI.importExisting(templateId.value, fd)
    _updateFromRead(res.data)
    return res.data
  }

  // 更新元数据
  async function updateMetadata(payload) {
    const res = await studioAPI.updateTemplate(templateId.value, payload)
    name.value = res.data.name
    description.value = res.data.description || ''
  }

  // 绑定
  async function bind(payload) {
    const res = await studioAPI.bindTemplate(templateId.value, payload)
    lessonId.value = res.data.lesson_id
    moduleId.value = res.data.module_id
  }

  // Cell 操作
  function addCell(type, afterIndex) {
    const id = _genId()
    const newCell = {
      id,
      type,
      source: '',
      order: afterIndex != null ? afterIndex + 1 : cells.value.length,
      student_editable: type === 'code',
      source_hidden: false,
    }
    cells.value = rebaseOrders([...cells.value, newCell])
    dirty.value = true
    saved.value = false
  }

  function duplicateCell(cellId) {
    const idx = cells.value.findIndex(c => c.id === cellId)
    if (idx < 0) return
    const src = cells.value[idx]
    const newCell = {
      ...src,
      id: _genId(),
      order: src.order + 1,
    }
    cells.value = rebaseOrders([...cells.value, newCell])
    dirty.value = true
    saved.value = false
  }

  function deleteCell(cellId) {
    cells.value = rebaseOrders(cells.value.filter(c => c.id !== cellId))
    dirty.value = true
    saved.value = false
  }

  function moveCell(cellId, direction) {
    const idx = cells.value.findIndex(c => c.id === cellId)
    if (idx < 0) return
    const target = direction === 'up' ? idx - 1 : idx + 1
    if (target < 0 || target >= cells.value.length) return
    const arr = [...cells.value]
    ;[arr[idx], arr[target]] = [arr[target], arr[idx]]
    cells.value = rebaseOrders(arr)
    dirty.value = true
    saved.value = false
  }

  function updateCellSource(cellId, source) {
    const cell = cells.value.find(c => c.id === cellId)
    if (!cell) return
    cell.source = source
    dirty.value = true
    saved.value = false
  }

  function setCellEditable(cellId, val) {
    const cell = cells.value.find(c => c.id === cellId)
    if (!cell || cell.type !== 'code') return
    cell.student_editable = val
    dirty.value = true
    saved.value = false
  }

  function setCellHidden(cellId, val) {
    const cell = cells.value.find(c => c.id === cellId)
    if (!cell || cell.type !== 'code') return
    cell.source_hidden = val
    dirty.value = true
    saved.value = false
  }

  function rebaseOrders(arr) {
    const sorted = [...arr].sort((a, b) => a.order - b.order)
    return sorted.map((c, i) => ({ ...c, order: i }))
  }

  // 保存草稿
  async function saveDraft() {
    if (conflict.value) return false
    saving.value = true
    error.value = null
    try {
      const payload = {
        draft_revision: draftRevision.value,
        cells: cells.value.map(c => ({
          id: c.id,
          type: c.type,
          source: c.source,
          order: c.order,
          student_editable: c.student_editable !== false,
          source_hidden: c.source_hidden === true,
        })),
      }
      const res = await studioAPI.saveDraft(templateId.value, payload)
      _updateFromRead(res.data)
      dirty.value = false
      saved.value = true
      return true
    } catch (e) {
      const code = e.response?.data?.detail?.code
      if (code === 'REVISION_CONFLICT') {
        conflict.value = true
        conflictMessage.value = e.response?.data?.detail?.message || '草稿已被其他会话修改，请刷新后重试'
      } else {
        error.value = { code: code || 'SAVE_FAILED', message: e.response?.data?.detail?.message || '保存失败' }
      }
      saved.value = false
      return false
    } finally {
      saving.value = false
    }
  }

  // 发布
  async function publish() {
    if (dirty.value) {
      const ok = await saveDraft()
      if (!ok) return null
    }
    saving.value = true
    try {
      const res = await studioAPI.publish(templateId.value)
      status.value = 'published'
      currentVersionId.value = res.data.id
      app.showToast(`已发布版本 ${res.data.version_number}`, 'success')
      return res.data
    } catch (e) {
      error.value = { code: 'PUBLISH_FAILED', message: e.response?.data?.detail?.message || '发布失败' }
      return null
    } finally {
      saving.value = false
    }
  }

  // 导出
  function downloadBlob(resp, filename) {
    const blob = resp.data instanceof Blob ? resp.data : new Blob([resp.data])
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  async function exportDraft() {
    try {
      const res = await studioAPI.exportDraft(templateId.value)
      downloadBlob(res, `template-${templateId.value}-draft.ipynb`)
    } catch {
      app.showToast('导出失败', 'error')
    }
  }

  async function exportVersion(versionId) {
    try {
      const res = await studioAPI.exportVersion(templateId.value, versionId)
      downloadBlob(res, `template-${templateId.value}-v${versionId}.ipynb`)
    } catch {
      app.showToast('导出失败', 'error')
    }
  }

  // 预览运行
  async function previewRun(cellId) {
    runningCellId.value = cellId
    try {
      const res = await studioAPI.previewRun(templateId.value, { cell_id: cellId })
      const cell = cells.value.find(c => c.id === cellId)
      if (cell) {
        cell._previewOutputs = {
          outputs: res.data.outputs,
          execution_time_ms: res.data.execution_time_ms,
        }
      }
      return res.data
    } catch (e) {
      const code = e.response?.data?.detail?.code
      if (code === 'KERNEL_INIT_FAILED') {
        app.showToast('隐藏 Cell 初始化失败，Kernel 已销毁', 'error')
      } else {
        app.showToast('预览执行失败', 'error')
      }
    } finally {
      runningCellId.value = null
    }
  }

  async function previewInterrupt() {
    try { await studioAPI.previewInterrupt(templateId.value) }
    catch { /* ignore */ }
  }

  async function previewReset() {
    try {
      await studioAPI.previewReset(templateId.value)
      cells.value.forEach(c => { c._previewOutputs = null })
    } catch { /* ignore */ }
  }

  function _updateFromRead(data) {
    if (data.draft_revision != null) {
      draftRevision.value = data.draft_revision
      draftRevisionSaved.value = data.draft_revision
    }
    if (data.draft_cells) cells.value = data.draft_cells.map(c => ({ ...c }))
    if (data.current_version_id != null) currentVersionId.value = data.current_version_id
    status.value = data.status || 'draft'
    name.value = data.name
    description.value = data.description || ''
  }

  function destroy() {
    cells.value.forEach(c => { c._previewOutputs = null })
  }

  return {
    templateId, name, description, status, draftRevision, draftRevisionSaved,
    cells, sortedCells, currentVersionId, lessonId, moduleId, ownerId,
    dirty, saving, saved, conflict, conflictMessage, error, studentPreview,
    executingCellId, runningCellId,
    open, create, importNew, importExisting, updateMetadata, bind,
    addCell, duplicateCell, deleteCell, moveCell,
    updateCellSource, setCellEditable, setCellHidden,
    saveDraft, publish, exportDraft, exportVersion,
    previewRun, previewInterrupt, previewReset,
    destroy,
  }
})
