import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { experimentsAPI } from '../api/experiments.js'
import { useAppStore } from './app.js'

export const useExperimentStore = defineStore('experiment', () => {
  const app = useAppStore()

  const moduleId = ref(null)
  const recordId = ref(null)
  const moduleName = ref('')
  const moduleDescription = ref('')
  const cells = ref([])         // [{id, source, order, outputs, isRunning}]
  const cellOrder = ref([])
  const executionCount = ref(0)
  const isDirty = ref(false)
  const isSaving = ref(false)

  // ── 加载 ──────────────────────────────────────

  async function openExperiment(mid) {
    moduleId.value = mid

    // 1. 获取模块信息
    const modRes = await experimentsAPI.getModule(mid)
    moduleName.value = modRes.data.name
    moduleDescription.value = modRes.data.description

    // 2. 确保有实验记录
    const recRes = await experimentsAPI.ensureRecord(mid)
    recordId.value = recRes.data.id

    // 3. 获取记录详情（含 cells）
    const detailRes = await experimentsAPI.getRecordDetail(recordId.value)
    const d = detailRes.data
    cells.value = d.cells || []
    cellOrder.value = d.cell_order || []
    executionCount.value = d.execution_count || 0

    // 4. 如果没有 cell，创建一个空白的
    if (cells.value.length === 0) {
      addCell()
    }

    isDirty.value = false
  }

  // ── Cell 操作 ─────────────────────────────────

  function addCell() {
    const id = crypto.randomUUID?.() || Date.now().toString(36) + Math.random().toString(36).slice(2)
    const cell = {
      id,
      source: '',
      order: cells.value.length,
      outputs: null,
      isRunning: false,
    }
    cells.value.push(cell)
    cellOrder.value.push(id)
    isDirty.value = true
  }

  function removeCell(cellId) {
    const idx = cells.value.findIndex(c => c.id === cellId)
    if (idx < 0) return
    if (cells.value.length <= 1) {
      // 至少保留一个空 cell
      cells.value[0].source = ''
      cells.value[0].outputs = null
      return
    }
    cells.value.splice(idx, 1)
    cellOrder.value = cellOrder.value.filter(id => id !== cellId)
    isDirty.value = true
  }

  function updateCellSource(cellId, source) {
    const cell = cells.value.find(c => c.id === cellId)
    if (cell) {
      cell.source = source
      isDirty.value = true
    }
  }

  // ── 执行 ──────────────────────────────────────

  async function executeCell(cellId) {
    const cell = cells.value.find(c => c.id === cellId)
    if (!cell) return

    cell.isRunning = true
    try {
      const res = await experimentsAPI.executeCell(recordId.value, cellId, cell.source)
      cell.outputs = {
        execution_count: res.data.execution_count,
        outputs: res.data.outputs,
        execution_time_ms: res.data.execution_time_ms,
      }
      executionCount.value = res.data.execution_count
    } catch (err) {
      if (err.response?.status === 409) {
        app.showToast('Kernel 正忙，请等待当前代码执行完成', 'warning')
      } else {
        app.showToast('执行失败：' + (err.response?.data?.detail || err.message), 'error')
      }
    } finally {
      cell.isRunning = false
    }
  }

  async function interruptKernel() {
    try {
      await experimentsAPI.interrupt(recordId.value)
      app.showToast('已中断', 'success')
    } catch {
      app.showToast('中断失败', 'error')
    }
  }

  async function restartKernel() {
    if (!confirm('确定要重启 Kernel 吗？所有输出将被清除，但代码会保留。')) return
    try {
      await experimentsAPI.restartKernel(recordId.value)
      // 清空所有 outputs
      for (const cell of cells.value) {
        cell.outputs = null
      }
      executionCount.value = 0
      app.showToast('Kernel 已重启', 'success')
    } catch {
      app.showToast('重启失败', 'error')
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
        cellSources[cell.id] = cell.source
      }
      await experimentsAPI.saveCells(recordId.value, cellSources, cellOrder.value)
      isDirty.value = false
    } catch {
      app.showToast('保存失败', 'error')
    } finally {
      isSaving.value = false
    }
  }

  // ── 手动保存（页面离开时调用） ─────────────────

  async function saveBeforeLeave() {
    if (isDirty.value) {
      await saveProgress()
    }
  }

  return {
    moduleId, recordId, moduleName, moduleDescription,
    cells, cellOrder, executionCount,
    isDirty, isSaving,
    openExperiment, addCell, removeCell, updateCellSource,
    executeCell, interruptKernel, restartKernel,
    saveProgress, saveBeforeLeave,
  }
})
