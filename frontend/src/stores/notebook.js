import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { notebooksAPI } from '../api/notebooks.js'
import { useAppStore } from './app.js'

export const useNotebookStore = defineStore('notebook', () => {
  const app = useAppStore()

  const lessonId = ref(null)
  const recordId = ref(null)
  const cells = ref([])         // {id, cell_type, source, rendered_html, outputs}
  const cellOrder = ref([])
  const recordStatus = ref('started')
  const templateOutdated = ref(false)
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
    recordStatus.value = res.data.status
    templateOutdated.value = res.data.template_outdated
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

  // ── 自动保存 ──────────────────────────────────

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
      // 清空所有 outputs
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

  // ── 重置 / 提交 ──────────────────────────────

  async function resetNotebook() {
    if (!confirm('确定要重置为教师模板吗？你当前的修改将丢失。')) return
    try {
      await notebooksAPI.reset(recordId.value)
      await openNotebook(lessonId.value)
      app.showToast('已重置为模板', 'success')
    } catch {
      app.showToast('重置失败', 'error')
    }
  }

  async function submitNotebook() {
    if (!confirm('确定要提交作业吗？提交后将生成不可变快照。')) return
    try {
      // 先保存
      await saveProgress()
      await notebooksAPI.submit(recordId.value)
      recordStatus.value = 'submitted'
      app.showToast('提交成功！', 'success')
    } catch {
      app.showToast('提交失败', 'error')
    }
  }

  async function handleTemplateUpgrade(action) {
    try {
      await notebooksAPI.upgradeTemplate(recordId.value, action)
      await openNotebook(lessonId.value)
      app.showToast(action === 'discard' ? '已加载新版本' : '已保留当前版本', 'success')
    } catch {
      app.showToast('操作失败', 'error')
    }
  }

  return {
    lessonId, recordId, cells, cellOrder, recordStatus,
    templateOutdated, isDirty, isSaving, executingCellId,
    openNotebook, updateCellSource, saveProgress,
    executeCell, interruptKernel, restartKernel,
    resetNotebook, submitNotebook, handleTemplateUpgrade,
  }
})
