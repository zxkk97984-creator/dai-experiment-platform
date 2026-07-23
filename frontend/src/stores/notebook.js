import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { notebooksAPI } from '../api/notebooks.js'
import { useAppStore } from './app.js'

export const useNotebookStore = defineStore('notebook', () => {
  const app = useAppStore()

  const lessonId = ref(null)
  const recordId = ref(null)
  const cells = ref([])         // {id, cell_type, source, rendered_html, outputs}
  const cellOrder = ref([])
  const isDirty = ref(false)
  const isSaving = ref(false)
  const executingCellId = ref(null)

  // ── 加载 ──────────────────────────────────────

  async function openNotebook(lid) {
    lessonId.value = lid
    const res = await notebooksAPI.get(lid)
    recordId.value = res.data.record_id
    cells.value = res.data.cells
    cellOrder.value = res.data.cell_order
    isDirty.value = false
  }

  // ── 编辑 ──────────────────────────────────────

  function updateCellSource(cellId, source) {
    const cell = cells.value.find(c => c.id === cellId)
    if (cell) {
      cell.source = source
      isDirty.value = true
    }
  }

  // ── 自动保存（30秒防抖）──────────────────────

  let saveTimer = null
  watch(cells, () => {
    if (isDirty.value && !isSaving.value) {
      clearTimeout(saveTimer)
      saveTimer = setTimeout(() => saveProgress(), 30000)
    }
  }, { deep: false })

  async function saveProgress() {
    if (!recordId.value || !isDirty.value) return
    isSaving.value = true
    try {
      const cellSources = {}
      for (const cell of cells.value) {
        if (cell.cell_type === 'code') {
          cellSources[cell.id] = cell.source
        }
      }
      await notebooksAPI.saveCells(recordId.value, cellSources)
      isDirty.value = false
    } catch {
      app.showToast('保存失败', 'error')
    } finally {
      isSaving.value = false
    }
  }

  // ── 执行 ──────────────────────────────────────

  async function executeCell(cellId) {
    const cell = cells.value.find(c => c.id === cellId)
    if (!cell || cell.cell_type !== 'code') return

    executingCellId.value = cellId
    try {
      const res = await notebooksAPI.executeCell(recordId.value, cellId, cell.source)
      cell.outputs = {
        outputs: res.data.outputs,
        execution_time_ms: res.data.execution_time_ms,
      }
    } catch (err) {
      if (err.response?.status === 409) {
        app.showToast('Kernel 正忙，请等待当前代码执行完成', 'warning')
      } else {
        app.showToast('执行失败', 'error')
      }
    } finally {
      executingCellId.value = null
    }
  }

  async function executeAllCells() {
    const codeCells = cells.value.filter(c => c.cell_type === 'code')
    if (codeCells.length === 0) return
    for (const cell of codeCells) {
      await executeCell(cell.id)
    }
  }

  async function interruptKernel() {
    try {
      await notebooksAPI.interrupt(recordId.value)
      app.showToast('已中断', 'success')
    } catch {
      app.showToast('中断失败', 'error')
    }
  }

  async function restartKernel() {
    try {
      await notebooksAPI.restartKernel(recordId.value)
      for (const cell of cells.value) {
        if (cell.cell_type === 'code') {
          cell.outputs = null
        }
      }
      app.showToast('Kernel 已重启', 'success')
    } catch {
      app.showToast('重启失败', 'error')
    }
  }

  return {
    lessonId, recordId, cells, cellOrder,
    isDirty, isSaving, executingCellId,
    openNotebook, updateCellSource, saveProgress,
    executeCell, executeAllCells, interruptKernel, restartKernel,
  }
})
