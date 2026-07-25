import { ref } from 'vue'
import { defineStore } from 'pinia'
import { experimentsAPI } from '../api/experiments.js'
import { useAppStore } from './app.js'

export const useExperimentStore = defineStore('experiment', () => {
  const app = useAppStore()

  const context = ref(null)
  const recordId = ref(null)
  const recordRevision = ref(0)
  const cells = ref([])
  const entryName = ref('')
  const entryDescription = ref('')

  const dirty = ref(false)
  const saving = ref(false)
  const saved = ref(false)
  const error = ref(null)
  const conflict = ref(false)
  const executingCellId = ref(null)

  const dirtySources = ref({})

  let debounceTimer = null
  let safetyInterval = null
  let pendingFlush = null

  // ── safety ──
  function _startSafety() {
    _stopSafety()
    safetyInterval = setInterval(() => {
      if (dirty.value && !conflict.value && !saving.value) {
        flushSave()
      }
    }, 30000)
  }

  function _stopSafety() {
    if (safetyInterval) { clearInterval(safetyInterval); safetyInterval = null }
  }

  // ── 加载 ──
  async function openLesson(lessonId, courseId) {
    context.value = { type: 'lesson', id: lessonId, courseId, returnPath: `/student/courses/${courseId}`, title: null }
    await _load(lessonId, null)
  }

  async function openModule(moduleId) {
    context.value = { type: 'module', id: moduleId, returnPath: '/student/experiments', title: null }
    await _load(null, moduleId)
  }

  async function _load(lessonId, moduleId) {
    clearTimeout(debounceTimer)
    _stopSafety()
    if (pendingFlush) {
      await pendingFlush
    }

    error.value = null
    conflict.value = false
    dirty.value = false
    saved.value = false
    dirtySources.value = {}

    const ensRes = lessonId != null
      ? await experimentsAPI.ensureForLesson(lessonId)
      : await experimentsAPI.ensureForModule(moduleId)
    recordId.value = ensRes.data.id
    recordRevision.value = ensRes.data.record_revision

    const detail = await experimentsAPI.getRecordDetail(recordId.value)
    const d = detail.data
    const raw = (d.cells || []).map(c => ({
      id: c.id, type: c.type || 'code', source: c.source || '',
      order: c.order || 0,
      student_editable: c.student_editable !== false,
      outputs: c.outputs || null, isRunning: false,
    }))
    raw.sort((a, b) => a.order - b.order)
    cells.value = raw
    entryName.value = d.entry_name || ''
    entryDescription.value = d.entry_description || ''
    if (context.value) context.value.title = entryName.value
    if (d.record_revision != null) recordRevision.value = d.record_revision
    saved.value = true
    _startSafety()
  }

  // ── 编辑 ──
  function updateCellSource(cellId, source) {
    const cell = cells.value.find(c => c.id === cellId)
    if (!cell || !cell.student_editable) return
    cell.source = source
    dirtySources.value = { ...dirtySources.value, [cellId]: source }
    dirty.value = true
    saved.value = false
    // conflict 不清除——只有 reload 才能清除
    if (!conflict.value) {
      error.value = null
      scheduleDebounce()
    }
  }

  function scheduleDebounce() {
    clearTimeout(debounceTimer)
    if (conflict.value) return
    debounceTimer = setTimeout(() => flushSave(), 1200)
  }

  // ── 串行保存 ──
  async function _drainDirtySources() {
    saving.value = true
    saved.value = false

    try {
      while (Object.keys(dirtySources.value).length > 0) {
        const sourcesToSave = { ...dirtySources.value }
        const revisionToSave = recordRevision.value

        try {
          const res = await experimentsAPI.saveCells(
            recordId.value,
            sourcesToSave,
            revisionToSave,
          )
          recordRevision.value = res.data.record_revision
        } catch (e) {
          const code = e.response?.data?.detail?.code
          if (code === 'REVISION_CONFLICT') {
            conflict.value = true
            error.value = {
              code: 'REVISION_CONFLICT',
              message: '记录已被他人修改，请刷新页面后重试',
            }
          } else {
            error.value = {
              code: code || 'SAVE_FAILED',
              message: e.response?.data?.detail?.message || '保存失败',
            }
          }
          dirty.value = true
          saved.value = false
          return false
        }

        const remaining = { ...dirtySources.value }
        for (const [cellId, source] of Object.entries(sourcesToSave)) {
          if (remaining[cellId] === source) {
            delete remaining[cellId]
          }
        }
        dirtySources.value = remaining
        dirty.value = Object.keys(remaining).length > 0
        saved.value = !dirty.value
        error.value = null
      }

      dirty.value = false
      saved.value = true
      return true
    } finally {
      saving.value = false
    }
  }

  function flushSave() {
    clearTimeout(debounceTimer)
    if (!recordId.value || (!dirty.value && !pendingFlush)) {
      return Promise.resolve(true)
    }
    if (conflict.value) {
      return Promise.resolve(false)
    }
    if (pendingFlush) {
      return pendingFlush
    }

    const trackedDrain = _drainDirtySources().finally(() => {
      if (pendingFlush === trackedDrain) {
        pendingFlush = null
      }
    })
    pendingFlush = trackedDrain
    return trackedDrain
  }

  // ── canNavigate 供路由守卫使用 ──
  async function canNavigate() {
    let savedSuccessfully = true
    if (dirty.value || saving.value || pendingFlush) {
      savedSuccessfully = await flushSave()
    }
    if (!savedSuccessfully || conflict.value) {
      return window.confirm(
        '保存失败（' + (error.value?.message || '未知错误') +
        '），确定离开吗？未保存的修改将丢失。',
      )
    }
    return true
  }

  // ── 执行 ──
  async function executeCell(cellId) {
    const cell = cells.value.find(c => c.id === cellId)
    if (!cell || cell.type !== 'code') return
    executingCellId.value = cellId
    try {
      const res = await experimentsAPI.executeCell(recordId.value, cellId, cell.source)
      cell.outputs = {
        outputs: res.data.outputs,
        execution_time_ms: res.data.execution_time_ms,
        execution_count: res.data.execution_count,
      }
    } catch (e) {
      if (e.response?.status === 409) app.showToast('Kernel 正忙，请等待', 'warning')
      else app.showToast('执行失败', 'error')
    } finally {
      executingCellId.value = null
    }
  }

  async function executeAllCells() {
    for (const cell of cells.value.filter(c => c.type === 'code')) {
      await executeCell(cell.id)
    }
  }

  async function interruptKernel() {
    try { await experimentsAPI.interrupt(recordId.value); app.showToast('已中断', 'success') }
    catch { app.showToast('中断失败', 'error') }
  }

  async function restartKernel() {
    try {
      await experimentsAPI.restart(recordId.value)
      for (const c of cells.value) { if (c.type === 'code') c.outputs = null }
      app.showToast('Kernel 已重启', 'success')
    } catch { app.showToast('重启失败', 'error') }
  }

  function destroy() {
    clearTimeout(debounceTimer)
    _stopSafety()
  }

  return {
    context, recordId, recordRevision, cells, entryName, entryDescription,
    dirty, saving, saved, error, conflict, executingCellId,
    openLesson, openModule,
    updateCellSource, flushSave, canNavigate,
    executeCell, executeAllCells, interruptKernel, restartKernel,
    destroy,
  }
})
