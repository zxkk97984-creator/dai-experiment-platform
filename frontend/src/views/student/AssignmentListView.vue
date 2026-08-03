<script setup>
// 任务中心（参考图 05）：作业 + 考试 + 实验聚合为统一任务列表。
// 全部数据来自既有 API（allSettled，单来源失败不整页报错）；
// 状态、分组、筛选、排序全部走 studentUi 纯函数，零伪造日期。

import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppLayout from '../../components/layout/AppLayout.vue'
import DashboardAsyncState from '../../components/dashboard/DashboardAsyncState.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import UiPanel from '../../components/ui/UiPanel.vue'
import { assignmentsAPI } from '../../api/assignments.js'
import { examsAPI } from '../../api/exams.js'
import { experimentsAPI } from '../../api/experiments.js'
import { coursesAPI } from '../../api/courses.js'
import {
  groupTasksByDeadline,
  normalizeAssignmentTask,
  normalizeExamTask,
  normalizeExperimentTask,
  taskStatus,
} from '../../utils/studentUi.js'

const router = useRouter()

const DAY = 86400000
const tasks = ref([])
const courseMap = ref({})
const loading = ref(true)
const error = ref(false)

const filters = reactive({ status: 'all', courseId: '', kind: '', time: 'all', sort: 'due' })

const timeFmt = new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
const kindLabel = { assignment: '作业', exam: '考试', experiment: '实验' }
const kindIcon = { assignment: 'assignment', exam: 'exam', experiment: 'experiment' }
const groupLabel = {
  overdue: '已逾期',
  today: '今天截止',
  tomorrow: '明天截止',
  this_week: '本周截止',
  later: '更晚',
  no_deadline: '无截止时间',
}
const groupIcon = {
  overdue: 'warning',
  today: 'clock',
  tomorrow: 'calendar',
  this_week: 'calendar',
  later: 'clock',
  no_deadline: 'clipboard',
}
const groupTone = {
  overdue: 'tone-danger',
  today: 'tone-warning',
  tomorrow: 'tone-primary',
  this_week: 'tone-primary',
  later: 'tone-neutral',
  no_deadline: 'tone-neutral',
}

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

const groups = computed(() => groupTasksByDeadline(filteredTasks.value, now()))

/** 主 CTA 仅给最紧急的逾期任务，其余为轮廓按钮 */
const mostUrgentId = computed(() => {
  const t = now()
  const overdue = filteredTasks.value
    .filter((task) => taskStatus(task, t) === 'overdue')
    .sort((a, b) => (a.dueAt ?? 0) - (b.dueAt ?? 0))
  return overdue[0]?.id ?? null
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
      <DashboardAsyncState
        :loading="loading"
        :error="error"
        :empty="filteredTasks.length === 0"
        empty-title="暂无任务"
        empty-body="没有符合条件的任务"
        @retry="loadAll"
      >
        <div class="task-groups">
          <section
            v-for="(items, key) in groups"
            :key="key"
            class="task-group"
            :class="{ 'is-hidden': items.length === 0 }"
          >
            <h3 class="task-group-title">
              <span class="group-icon" :class="groupTone[key]" aria-hidden="true">
                <AppIcon :name="groupIcon[key]" :size="16" />
              </span>
              <span class="group-label">{{ groupLabel[key] }}</span>
              <span class="group-count">{{ items.length }}</span>
            </h3>
            <div class="task-list">
              <article
                v-for="task in items"
                :key="task.kind + '-' + task.id"
                class="task-row"
              >
                <span class="task-kind-icon" aria-hidden="true">
                  <AppIcon :name="kindIcon[task.kind]" :size="18" />
                </span>
                <div class="task-row-main">
                  <span class="task-row-title">{{ task.title }}</span>
                  <span class="task-row-course">{{ task.courseTitle || '—' }}</span>
                </div>
                <span class="task-kind-label">{{ kindLabel[task.kind] || task.kind }}</span>
                <span class="task-deadline">{{ task.dueAt ? formatTime(task.dueAt) : '—' }}</span>
                <span class="task-status-pill" :class="'status-' + statusTone(task)">
                  {{ statusText(task) }}
                </span>
                <button
                  type="button"
                  class="task-row-cta"
                  :class="task.id === mostUrgentId ? 'btn-primary' : 'btn-outline'"
                  @click="go(task.route)"
                >
                  进入
                </button>
              </article>
            </div>
          </section>
        </div>
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

/* ── 分组 ────────────────────────────────────────────────────── */
.task-groups { display: flex; flex-direction: column; gap: 20px; }
.task-group.is-hidden { display: none; }
.task-group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 10px;
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--ink);
}
.group-icon {
  width: 28px; height: 28px;
  border-radius: var(--radius-control);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.group-icon.tone-danger { background: var(--danger-light); color: var(--danger); }
.group-icon.tone-warning { background: var(--warning-light); color: var(--warning); }
.group-icon.tone-primary { background: var(--primary-light); color: var(--primary); }
.group-icon.tone-neutral { background: var(--surface-raised); color: var(--text-secondary); }
.group-count {
  padding: 1px 8px;
  border-radius: var(--radius-full);
  background: var(--surface-raised);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-secondary);
}

/* ── 任务行（96–102px） ──────────────────────────────────────── */
.task-list { display: flex; flex-direction: column; gap: 10px; }
.task-row {
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 96px;
  padding: 14px 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}
.task-kind-icon {
  flex-shrink: 0;
  width: 42px; height: 42px;
  border-radius: var(--radius-control);
  background: var(--primary-light);
  color: var(--primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.task-row-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.task-row-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
}
.task-row-course {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
.task-kind-label {
  flex-shrink: 0;
  min-width: 44px;
  font-size: var(--text-xs);
  color: var(--text-secondary);
}
.task-deadline {
  flex-shrink: 0;
  min-width: 108px;
  font-size: var(--text-xs);
  color: var(--text-secondary);
  font-family: var(--font-mono);
}
.task-status-pill {
  flex-shrink: 0;
  min-width: 52px;
  text-align: center;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: 600;
}
.task-status-pill.status-pending { color: var(--text-secondary); background: var(--surface-raised); }
.task-status-pill.status-danger { color: var(--danger); background: var(--danger-light); }
.task-status-pill.status-success { color: var(--success); background: var(--success-light); }

.task-row-cta {
  flex-shrink: 0;
  height: 40px;
  padding: 0 20px;
  font-weight: 600;
  border-radius: var(--radius-control);
}
.btn-outline {
  background: var(--surface);
  border: 1px solid var(--border-strong);
  color: var(--primary);
  cursor: pointer;
}
.btn-outline:hover { background: var(--primary-light); border-color: var(--primary-soft); }

@media (max-width: 767.98px) {
  .task-row { flex-wrap: wrap; gap: 10px; }
  .task-row-main { flex: 1 1 100%; }
}
</style>
