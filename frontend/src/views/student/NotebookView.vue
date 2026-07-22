<script setup>
import { onMounted, onBeforeUnmount, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import MarkdownCell from '../../components/notebook/MarkdownCell.vue'
import CodeCell from '../../components/notebook/CodeCell.vue'
import { useNotebookStore } from '../../stores/notebook.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const router = useRouter()
const store = useNotebookStore()
const app = useAppStore()

const courseId = computed(() => route.params.id)
const lessonId = computed(() => route.params.lid)

const statusText = computed(() => {
  if (store.isSaving) return '保存中...'
  if (store.isDirty) return '未保存'
  return '已保存'
})

const canInteract = computed(() => store.recordStatus !== 'submitted')

onMounted(async () => {
  try {
    await store.openNotebook(lessonId.value)
  } catch {
    app.showToast('加载笔记本失败', 'error')
    router.replace(`/student/courses/${courseId.value}`)
  }
})

onBeforeUnmount(() => {
  if (store.isDirty) {
    store.saveProgress()
  }
})

function goBack() {
  router.push(`/student/courses/${courseId.value}`)
}

function getExecutionCount(cellId) {
  const cell = store.cells.find(c => c.id === cellId)
  if (!cell?.outputs) return null
  return cell.outputs.execution_count || null
}
</script>

<template>
  <AppLayout>
    <!-- 面包屑 -->
    <div class="notebook-header">
      <button class="back-btn" @click="goBack">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10 3L5 8l5 5"/>
        </svg>
        返回课程
      </button>
      <div class="header-right">
        <span class="save-status" :class="{ dirty: store.isDirty, saving: store.isSaving }">
          <span class="status-dot"></span>
          {{ statusText }}
        </span>
        <span v-if="store.templateOutdated" class="badge-warn">课件已更新</span>
        <span v-if="store.recordStatus === 'submitted'" class="badge-done">已提交</span>
      </div>
    </div>

    <!-- 模板过期提示 -->
    <div v-if="store.templateOutdated" class="template-update-banner">
      <p>⚠ 教师的课件已更新。你可以选择保留当前进度继续使用旧版本，或放弃进度加载新版本。</p>
      <div class="banner-actions">
        <button class="btn-ghost btn-sm" @click="store.handleTemplateUpgrade('keep')">保留我的进度</button>
        <button class="btn-accent btn-sm" @click="store.handleTemplateUpgrade('discard')">加载新版本</button>
      </div>
    </div>

    <!-- 操作栏 -->
    <div class="action-bar">
      <button class="btn-ghost btn-sm" @click="store.executeAllCells" :disabled="!canInteract">
        ▶ 全部运行
      </button>
      <button class="btn-ghost btn-sm" @click="store.interruptKernel" :disabled="!store.executingCellId">
        ⏹ 中断
      </button>
      <button class="btn-ghost btn-sm" @click="store.restartKernel">
        ↻ 重启 Kernel
      </button>
      <div class="action-spacer"></div>
      <button class="btn-ghost btn-sm" @click="store.saveProgress" :disabled="store.isSaving">
        💾 保存
      </button>
      <button class="btn-ghost btn-sm" @click="store.resetNotebook" :disabled="!canInteract">
        ↺ 重置
      </button>
      <button class="btn-accent btn-sm" @click="store.submitNotebook" :disabled="!canInteract">
        ✓ 提交
      </button>
    </div>

    <!-- Cell 列表 -->
    <div v-if="store.cells.length === 0" class="empty-state">
      <p>暂无内容</p>
    </div>

    <div v-for="cell in store.cells" :key="cell.id" class="cell-wrapper">
      <MarkdownCell v-if="cell.cell_type === 'markdown'" :cell="cell" />
      <CodeCell
        v-else-if="cell.cell_type === 'code'"
        :cell="cell"
        :execution-count="getExecutionCount(cell.id)"
        :disabled="!canInteract"
        :is-executing="store.executingCellId === cell.id"
        @execute="store.executeCell"
        @update:source="store.updateCellSource"
      />
    </div>

    <!-- 底部操作 -->
    <div class="bottom-bar">
      <button class="btn-ghost btn-sm" @click="store.resetNotebook" :disabled="!canInteract">
        ↺ 重置模板
      </button>
      <button class="btn-ghost btn-sm" @click="store.saveProgress" :disabled="store.isSaving">
        💾 保存进度
      </button>
      <button class="btn-accent btn-sm" @click="store.submitNotebook" :disabled="!canInteract">
        ✓ 提交作业
      </button>
    </div>
  </AppLayout>
</template>

<style scoped>
.notebook-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  background: none;
  border: none;
  cursor: pointer;
}

.back-btn:hover { color: var(--text); }

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.save-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--success);
}

.save-status.dirty .status-dot { background: var(--warning); }
.save-status.saving .status-dot { animation: pulse 0.8s infinite; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.badge-warn {
  font-size: var(--text-xs);
  padding: 2px 8px;
  border-radius: 12px;
  background: var(--warning-light);
  color: #7C5E0A;
  font-weight: 500;
}

.badge-done {
  font-size: var(--text-xs);
  padding: 2px 8px;
  border-radius: 12px;
  background: var(--success-light);
  color: var(--success-dark, #166534);
  font-weight: 500;
}

.template-update-banner {
  background: var(--warning-light);
  border: 1px solid var(--warning);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
}

.template-update-banner p {
  margin: 0 0 var(--space-3);
  font-size: var(--text-sm);
  color: #7C5E0A;
}

.banner-actions {
  display: flex;
  gap: var(--space-3);
}

.action-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}

.action-spacer { flex: 1; }

.empty-state {
  text-align: center;
  padding: var(--space-12) var(--space-6);
  color: var(--text-secondary);
}

.cell-wrapper {
  /* spacing handled by cell components */
}

.bottom-bar {
  display: flex;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-6) 0;
  border-top: 1px solid var(--border);
  margin-top: var(--space-4);
}

/* Buttons */
.btn-accent {
  background: var(--accent);
  color: #fff;
  border: 1px solid var(--accent);
  padding: 6px 16px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast);
}

.btn-accent:hover:not(:disabled) {
  background: var(--accent-dark);
  border-color: var(--accent-dark);
}

.btn-accent:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-ghost {
  background: none;
  border: 1px solid var(--border);
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-fast);
}

.btn-ghost:hover:not(:disabled) {
  border-color: var(--border-strong);
  color: var(--text);
}

.btn-ghost:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-sm { font-size: var(--text-xs); }
</style>
