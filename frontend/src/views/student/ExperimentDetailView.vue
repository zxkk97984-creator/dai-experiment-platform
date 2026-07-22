<script setup>
import { onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import CodeCell from '../../components/notebook/CodeCell.vue'
import { useExperimentStore } from '../../stores/experiment.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const router = useRouter()
const app = useAppStore()
const store = useExperimentStore()

onMounted(async () => {
  try {
    await store.openExperiment(route.params.id)
  } catch {
    app.showToast('加载实验失败', 'error')
  }
})

// 页面离开前保存
onBeforeUnmount(() => {
  store.saveBeforeLeave()
})

function goBack() {
  store.saveBeforeLeave()
  router.push('/student/experiments')
}

function handleRun(cellId) {
  store.executeCell(cellId)
}

function handleUpdateSource(cellId, source) {
  store.updateCellSource(cellId, source)
}

function handleRestart() {
  store.restartKernel()
}
</script>

<template>
  <AppLayout>
    <!-- 返回按钮 -->
    <button class="btn-ghost btn-sm back-btn" @click="goBack">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10 3L5 8l5 5"/>
      </svg>
      返回实验列表
    </button>

    <!-- 实验标题 -->
    <div class="experiment-hero">
      <h1 class="experiment-title">
        <span class="experiment-icon">🧪</span>
        {{ store.moduleName }}
      </h1>
      <p v-if="store.moduleDescription" class="experiment-desc">{{ store.moduleDescription }}</p>
      <div class="experiment-meta">
        <span class="meta-badge">执行次数：{{ store.executionCount }}</span>
        <span class="meta-badge">代码单元格：{{ store.cells.length }}</span>
      </div>
    </div>

    <!-- Cell 列表 -->
    <div class="cells-area">
      <CodeCell
        v-for="cell in store.cells"
        :key="cell.id"
        :cell="cell"
        :execution-count="cell.outputs?.execution_count ?? null"
        :is-executing="cell.isRunning"
        @execute="handleRun"
        @update:source="handleUpdateSource"
      >
        <!-- 删除 cell 按钮插在工具栏区域？用自定义方式 -->
      </CodeCell>
    </div>

    <!-- 操作栏 -->
    <div class="action-bar">
      <button class="btn-add-cell" @click="store.addCell()">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <path d="M7 3v8M3 7h8"/>
        </svg>
        添加代码单元格
      </button>

      <div class="action-right">
        <button class="btn-restart" @click="handleRestart">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2 7a5 5 0 0 1 9.5-2"/><path d="M12 2v3H9"/><path d="M12 7a5 5 0 0 1-9.5 2"/><path d="M2 12v-3h3"/>
          </svg>
          重启 Kernel
        </button>
      </div>
    </div>

    <!-- 空状态提示 -->
    <div v-if="store.cells.length === 0" class="empty-hint">
      <p>点击「添加代码单元格」开始编写 Python 代码</p>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ── 返回 ───────────────────────────────── */
.back-btn {
  display: inline-flex; align-items: center; gap: 4px;
  color: var(--text-secondary); font-size: var(--text-sm);
  margin-bottom: var(--space-4);
}
.back-btn:hover { color: var(--text); }

/* ── 标题区 ─────────────────────────────── */
.experiment-hero {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  margin-bottom: var(--space-4);
}
.experiment-title {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 var(--space-3);
  letter-spacing: -0.01em;
  display: flex; align-items: center; gap: 8px;
}
.experiment-icon { font-size: 24px; }
.experiment-desc {
  font-size: var(--text-sm);
  color: var(--text);
  line-height: 1.7;
  margin-bottom: var(--space-3);
}
.experiment-meta { display: flex; gap: var(--space-3); }
.meta-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 10px;
  font-size: var(--text-xs);
  color: var(--text-secondary);
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: 9999px;
}

/* ── Cells ──────────────────────────────── */
.cells-area {
  margin-bottom: var(--space-4);
}

/* ── 操作栏 ─────────────────────────────── */
.action-bar {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}

.btn-add-cell {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.btn-add-cell:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-light);
}

.action-right { display: flex; gap: var(--space-3); }

.btn-restart {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.btn-restart:hover {
  border-color: var(--warning);
  color: var(--warning);
  background: var(--warning-light);
}

/* ── 空状态 ─────────────────────────────── */
.empty-hint {
  text-align: center; padding: var(--space-8);
  color: var(--text-secondary); font-size: var(--text-sm);
}

/* ── 响应式 ─────────────────────────────── */
@media (max-width: 768px) {
  .action-bar { flex-direction: column; }
  .action-right { width: 100%; }
  .btn-add-cell, .btn-restart { width: 100%; justify-content: center; }
}
</style>
