<script setup>
// 任务中心：作业 + 考试 + 实验聚合为统一任务表格。
// 全部数据来自既有 API（allSettled，单来源失败不整页报错）；
// 状态、筛选、排序走 studentUi 纯函数，零伪造日期。

import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import AppLayout from '../../components/layout/AppLayout.vue'
import DashboardAsyncState from '../../components/dashboard/DashboardAsyncState.vue'
import UiStatusPill from '../../components/ui/UiStatusPill.vue'
import { assignmentsAPI } from '../../api/assignments.js'
import { examsAPI } from '../../api/exams.js'
import { experimentsAPI } from '../../api/experiments.js'
import { coursesAPI } from '../../api/courses.js'
import { normalizeAssignmentTask, normalizeExamTask, normalizeExperimentTask, taskStatus } from '../../utils/studentUi.js'

const router = useRouter()

const DAY = 86400000
const tasks = ref([])
const courseMap = ref({})
const loading = ref(true)
const error = ref(false)
const page = ref(1)
const pageSize = 10

const filters = reactive({ status: 'all', courseId: '', kind: '', time: 'all', sort: 'due' })

const timeFmt = new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
const kindLabel = { assignment: '作业', exam: '考试', experiment: '实验' }

const now = () => new Date()

async function loadAll() {
  loading.value = true
  error.value = false
  const [aRes, eRes, xRes, cRes] = await Promise.allSettled([
    assignmentsAPI.list(),
    examsAPI.list(),
    experimentsAPI.listRecords(),
    coursesAPI.list(),
  ])
  const courses = cRes.status === 'fulfilled' ? (cRes.value.data?.items || cRes.value.data || []) : []
  courseMap.value = Object.fromEntries(courses.map((c) => [c.id, c]))

  const flat = []
  const t = now()
  if (aRes.status === 'fulfilled') {
    for (const item of aRes.value.data?.items || aRes.value.data || []) {
      flat.push(normalizeAssignmentTask(item, courseMap.value, t))
    }
  }
  if (eRes.status === 'fulfilled') {
    for (const item of eRes.value.data?.items || eRes.value.data || []) {
      flat.push(normalizeExamTask(item, courseMap.value, t))
    }
  }
  if (xRes.status === 'fulfilled') {
    for (const item of xRes.value.data?.items || xRes.value.data || []) {
      flat.push(normalizeExperimentTask(item, courseMap.value, t))
    }
  }
  // 无法生成合法路由的任务直接丢弃，不渲染死链接
  tasks.value = flat.filter((task) => task.route)
  if (aRes.status !== 'fulfilled' && eRes.status !== 'fulfilled' && xRes.status !== 'fulfilled') {
    error.value = true
  }
  loading.value = false
}

const statusCounts = computed(() => {
  const counts = { all: tasks.value.length, pending: 0, overdue: 0, submitted: 0 }
  const t = now()
  for (const task of tasks.value) {
    const s = taskStatus(task, t)
    if (s === 'overdue') counts.overdue++
    else if (s === 'submitted') counts.submitted++
    else counts.pending++
  }
  return counts
})

/** 未提交任务中最早的未来截止（真实最近截止） */
const nearestDeadline = computed(() => {
  const t = now()
  const ts = tasks.value
    .filter((task) => taskStatus(task, t) !== 'submitted' && task.dueAt != null)
    .map((task) => task.dueAt)
    .sort((a, b) => a - b)
  return ts[0] ?? null
})

const filteredTasks = computed(() => {
  let list = tasks.value
  const t = now()
  if (filters.status !== 'all') list = list.filter((task) => taskStatus(task, t) === filters.status)
  if (filters.courseId) list = list.filter((task) => String(task.courseId) === filters.courseId)
  if (filters.kind) list = list.filter((task) => task.kind === filters.kind)
  if (filters.time === 'today') {
    const start = new Date()
    start.setHours(0, 0, 0, 0)
    list = list.filter((task) => task.dueAt != null && task.dueAt >= start.getTime() && task.dueAt < start.getTime() + DAY)
  } else if (filters.time === 'week') {
    const start = new Date()
    start.setHours(0, 0, 0, 0)
    list = list.filter((task) => task.dueAt != null && task.dueAt < start.getTime() + 7 * DAY)
  }
  if (filters.sort === 'due') {
    list = [...list].sort((a, b) => (a.dueAt ?? Infinity) - (b.dueAt ?? Infinity))
  } else if (filters.sort === 'course') {
    list = [...list].sort((a, b) => (a.courseTitle || '').localeCompare(b.courseTitle || ''))
  } else if (filters.sort === 'title') {
    list = [...list].sort((a, b) => a.title.localeCompare(b.title))
  }
  return list
})

const pageCount = computed(() => Math.max(1, Math.ceil(filteredTasks.value.length / pageSize)))
const paginatedTasks = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredTasks.value.slice(start, start + pageSize)
})
const visiblePages = computed(() => {
  const start = Math.max(1, Math.min(page.value - 2, pageCount.value - 4))
  const end = Math.min(pageCount.value, start + 4)
  return Array.from({ length: end - start + 1 }, (_, index) => start + index)
})

const courseOptions = computed(() => {
  const seen = new Map()
  for (const task of tasks.value) {
    if (task.courseId != null) seen.set(task.courseId, task.courseTitle)
  }
  return [...seen.entries()].map(([id, title]) => ({ id: String(id), title }))
})

function statusText(task) {
  const s = taskStatus(task, now())
  if (s === 'submitted') return '已提交'
  if (s === 'overdue') return '已逾期'
  return '待办'
}

function statusTone(task) {
  const s = taskStatus(task, now())
  if (s === 'submitted') return 'success'
  if (s === 'overdue') return 'danger'
  return 'pending'
}

function resetFilters() {
  filters.status = 'all'
  filters.courseId = ''
  filters.kind = ''
  filters.time = 'all'
  filters.sort = 'due'
}

function goToPage(value) {
  page.value = Math.min(Math.max(value, 1), pageCount.value)
}

function go(route) {
  if (route === '/student' || route.startsWith('/student/')) {
    router.push(route)
  }
}

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : timeFmt.format(date)
}

watch(filters, () => {
  page.value = 1
})

watch(pageCount, (count) => {
  if (page.value > count) page.value = count
})

onMounted(loadAll)
</script>

<template>
  <AppLayout>
    <div class="page">
      <!-- 页头 -->
      <header class="page-head">
        <div>
          <h1 class="page-title">任务中心</h1>
          <p class="page-sub">
            <span class="task-count">{{ statusCounts.all }} 项开放任务</span>
            <template v-if="nearestDeadline">
              · 最近截止 <span class="nearest-deadline">{{ formatTime(nearestDeadline) }}</span>
            </template>
          </p>
        </div>
      </header>

      <!-- 状态标签卡（58px） -->
      <div class="status-tabs" role="tablist" aria-label="任务状态">
        <button
          v-for="tab in [
            { key: 'all', label: '全部' },
            { key: 'pending', label: '待办' },
            { key: 'overdue', label: '逾期' },
            { key: 'submitted', label: '已完成' },
          ]"
          :key="tab.key"
          type="button"
          class="status-tab"
          :class="{ active: filters.status === tab.key }"
          role="tab"
          :aria-selected="filters.status === tab.key"
          @click="filters.status = tab.key"
        >
          {{ tab.label }}
          <span class="tab-count">{{ statusCounts[tab.key] }}</span>
        </button>
      </div>

      <!-- 筛选卡（72–76px） -->
      <div class="filter-card">
        <label class="filter-field">
          <span class="filter-label">课程</span>
          <select v-model="filters.courseId" class="filter-course" aria-label="按课程筛选">
            <option value="">全部课程</option>
            <option v-for="c in courseOptions" :key="c.id" :value="c.id">{{ c.title }}</option>
          </select>
        </label>
        <label class="filter-field">
          <span class="filter-label">类型</span>
          <select v-model="filters.kind" class="filter-kind" aria-label="按类型筛选">
            <option value="">全部类型</option>
            <option value="assignment">作业</option>
            <option value="exam">考试</option>
            <option value="experiment">实验</option>
          </select>
        </label>
        <label class="filter-field">
          <span class="filter-label">时间</span>
          <select v-model="filters.time" class="filter-time" aria-label="按时间筛选">
            <option value="all">全部时间</option>
            <option value="today">今天截止</option>
            <option value="week">未来 7 天</option>
          </select>
        </label>
        <label class="filter-field">
          <span class="filter-label">排序</span>
          <select v-model="filters.sort" class="filter-sort" aria-label="排序方式">
            <option value="due">截止时间</option>
            <option value="course">课程</option>
            <option value="title">标题</option>
          </select>
        </label>
        <button type="button" class="btn-outline reset-btn" @click="resetFilters">重置</button>
      </div>

      <!-- 任务区 -->
      <div class="task-catalog-heading">
        <h2>全部任务</h2>
        <span>共 {{ filteredTasks.length }} 个</span>
      </div>

      <DashboardAsyncState
        :loading="loading"
        :error="error"
        :empty="filteredTasks.length === 0"
        empty-title="暂无任务"
        empty-body="没有符合条件的任务"
        @retry="loadAll"
      >
        <div class="table-shell">
          <table class="task-table">
            <thead>
              <tr>
                <th>任务名称</th>
                <th>所属课程</th>
                <th>类型</th>
                <th>状态</th>
                <th>截止时间</th>
                <th class="action-column">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in paginatedTasks" :key="task.kind + '-' + task.id">
                <td data-label="任务名称">
                  <strong class="task-name" :title="task.title">{{ task.title }}</strong>
                </td>
                <td data-label="所属课程" class="task-course">{{ task.courseTitle || '—' }}</td>
                <td data-label="类型" class="task-kind">{{ kindLabel[task.kind] || task.kind }}</td>
                <td data-label="状态">
                  <UiStatusPill :tone="statusTone(task)" :label="statusText(task)" />
                </td>
                <td data-label="截止时间" class="task-deadline">
                  {{ task.dueAt ? formatTime(task.dueAt) : '—' }}
                </td>
                <td data-label="操作" class="action-column">
                  <button type="button" class="task-action" @click="go(task.route)">进入</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <nav class="pagination" aria-label="任务分页">
          <span class="pagination-total">共 {{ filteredTasks.length }} 条</span>
          <div class="pagination-controls">
            <button
              type="button"
              class="page-arrow"
              :disabled="page === 1"
              aria-label="上一页"
              @click="goToPage(page - 1)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg>
            </button>
            <button
              v-for="pageNumber in visiblePages"
              :key="pageNumber"
              type="button"
              class="page-number"
              :class="{ active: pageNumber === page }"
              :aria-current="pageNumber === page ? 'page' : undefined"
              @click="goToPage(pageNumber)"
            >
              {{ pageNumber }}
            </button>
            <button
              type="button"
              class="page-arrow"
              :disabled="page === pageCount"
              aria-label="下一页"
              @click="goToPage(page + 1)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"></path></svg>
            </button>
          </div>
          <span class="page-size">10 条/页</span>
        </nav>
      </DashboardAsyncState>
    </div>
  </AppLayout>
</template>

<style scoped>
.page { display: flex; flex-direction: column; gap: 20px; }

/* ── 页头 ─────────────────────────────────────────────────────── */
.page-head { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title {
  margin: 0 0 6px;
  font-size: 30px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.02em;
  line-height: 1.2;
}
.page-sub { margin: 0; font-size: var(--text-sm); color: var(--text-secondary); }

/* ── 状态标签卡（58px） ──────────────────────────────────────── */
.status-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 58px;
  padding: 0 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  overflow-x: auto;
}
.status-tab {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 18px;
  background: transparent;
  border: none;
  border-radius: var(--radius-control);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
}
.status-tab.active {
  background: var(--primary-light);
  color: var(--primary);
  font-weight: 600;
}
.tab-count {
  padding: 1px 8px;
  border-radius: var(--radius-full);
  background: var(--surface-raised);
  font-size: var(--text-xs);
  font-weight: 600;
}
.status-tab.active .tab-count { background: var(--primary-soft); }

/* ── 筛选卡（72–76px） ───────────────────────────────────────── */
.filter-card {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  min-height: 72px;
  padding: 14px 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}
.filter-field { display: flex; flex-direction: column; gap: 4px; }
.filter-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  font-weight: 500;
}
.filter-field select {
  width: auto;
  min-width: 120px;
  padding: 7px 10px;
  font-size: var(--text-sm);
  border-radius: var(--radius-control);
}
.reset-btn {
  padding: 8px 16px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-control);
  background: var(--surface);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  cursor: pointer;
}
.reset-btn:hover { background: var(--primary-light); color: var(--primary); }

/* ── 任务表格 ────────────────────────────────────────────────── */
.task-catalog-heading {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: -6px;
}
.task-catalog-heading h2 {
  margin: 0;
  color: var(--ink);
  font-size: 18px;
  font-weight: 650;
}
.task-catalog-heading span {
  color: var(--text-secondary);
  font-size: 13px;
}

.table-shell {
  overflow: hidden;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}
.task-table {
  width: 100%;
  margin: 0;
  border-collapse: collapse;
  table-layout: fixed;
}
.task-table th {
  height: 46px;
  padding: 0 18px;
  background: #f8fafc;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  text-align: left;
}
.task-table th:first-child { width: 25%; }
.task-table th:nth-child(2) { width: 23%; }
.task-table th:nth-child(3) { width: 10%; }
.task-table th:nth-child(4) { width: 12%; }
.task-table th:nth-child(5) { width: 18%; }
.task-table th:last-child { width: 12%; }
.task-table td {
  height: 60px;
  padding: 0 18px;
  border-top: 1px solid var(--border);
  color: var(--text-secondary);
  font-size: 13px;
  vertical-align: middle;
}
.task-table tbody tr { transition: background var(--duration-fast); }
.task-table tbody tr:hover { background: #f8fbff; }
.task-name {
  display: block;
  overflow: hidden;
  color: var(--ink);
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-course {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-kind { color: var(--text-secondary); }
.task-deadline {
  color: var(--text-secondary);
  font-family: var(--font-mono);
  white-space: nowrap;
}
.action-column { text-align: right !important; }
.task-action {
  min-height: 32px;
  padding: 6px 16px;
  border: 1px solid var(--primary-soft);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.task-action:hover {
  border-color: var(--primary);
  background: var(--primary-light);
}

/* ── 分页 ────────────────────────────────────────────────────── */
.pagination {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  min-height: 40px;
  color: var(--text-secondary);
  font-size: 12px;
}
.pagination-controls { display: flex; gap: 8px; }
.pagination button {
  width: 34px;
  height: 34px;
  min-width: 34px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--text-secondary);
  font-size: 12px;
}
.pagination button:hover:not(:disabled) {
  border-color: var(--primary-soft);
  color: var(--primary);
}
.pagination button.active {
  border-color: var(--primary);
  background: var(--primary);
  color: #fff;
}
.pagination button:disabled { cursor: not-allowed; opacity: .45; }
.pagination svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.page-size { justify-self: end; }

.btn-outline {
  background: var(--surface);
  border: 1px solid var(--border-strong);
  color: var(--primary);
  cursor: pointer;
}
.btn-outline:hover { background: var(--primary-light); border-color: var(--primary-soft); }

@media (max-width: 767.98px) {
  .page { gap: 16px; }
  .page-title { font-size: 24px; }
  .filter-card { align-items: stretch; gap: 12px; padding: 14px; }
  .filter-field, .filter-field select { width: 100%; }
  .reset-btn { width: 100%; }
  .table-shell { overflow: visible; border: 0; background: transparent; box-shadow: none; }
  .task-table, .task-table tbody { display: block; }
  .task-table thead { display: none; }
  .task-table tr {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 12px 18px;
    margin-bottom: 10px;
    padding: 18px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-xs);
  }
  .task-table td {
    display: flex;
    width: auto;
    height: auto;
    min-width: 0;
    align-items: center;
    gap: 8px;
    padding: 0;
    border: 0;
    text-align: left !important;
  }
  .task-table td::before {
    flex: 0 0 auto;
    content: attr(data-label);
    color: var(--text-tertiary);
    font-size: 12px;
  }
  .task-table td:first-child,
  .task-table td:nth-child(2),
  .task-table td:nth-child(5) { grid-column: 1 / -1; }
  .task-table td:first-child::before { display: none; }
  .task-table .action-column { justify-self: end; }
  .task-name { white-space: normal; }
  .task-course { white-space: normal; }
  .pagination { grid-template-columns: 1fr auto; }
  .pagination-total { display: none; }
  .pagination-controls { justify-self: start; }
}

@media (prefers-reduced-motion: reduce) {
  .task-table tbody tr { transition: none; }
}
</style>
