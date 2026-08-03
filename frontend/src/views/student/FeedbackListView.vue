<script setup>
// 提交与反馈（参考图 01）：以 dashboardAPI.student().recent_feedback 为真实来源
// 的“最近提交与反馈”列表——不做历史档案式声称。
// 状态标签、组合筛选、分页全部由计算属性完成，零伪造数据。

import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppLayout from '../../components/layout/AppLayout.vue'
import DashboardAsyncState from '../../components/dashboard/DashboardAsyncState.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import { dashboardAPI } from '../../api/dashboard.js'
import { feedbackStatus, filterFeedback } from '../../utils/studentUi.js'

const router = useRouter()

const DAY = 86400000
const items = ref([])
const loading = ref(true)
const error = ref(false)

const filters = reactive({ status: 'all', courseId: '', query: '', time: 'all' })
const page = ref(1)
const pageSize = ref(10)

const timeFmt = new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
const statusLabel = { pending: '等待评分', needs_revision: '需修改', passed: '已通过' }
const statusIcon = { pending: 'clock', needs_revision: 'close', passed: 'check' }
const statusTone = { pending: 'warning', needs_revision: 'danger', passed: 'success' }
const kindLabel = { assignment: '作业', exam: '考试', experiment: '实验' }

async function loadFeedback() {
  loading.value = true
  error.value = false
  try {
    const { data } = await dashboardAPI.student()
    items.value = data.recent_feedback || []
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

const courseOptions = computed(() => {
  const seen = new Map()
  for (const item of items.value) {
    if (item.course_id != null) seen.set(item.course_id, item.course_title)
    else if (item.course_title) seen.set(item.course_title, item.course_title)
  }
  return [...seen.entries()].map(([id, title]) => ({ id: String(id), title }))
})

const statusCounts = computed(() => {
  const counts = { all: items.value.length, pending: 0, needs_revision: 0, passed: 0 }
  for (const item of items.value) {
    counts[feedbackStatus(item)]++
  }
  return counts
})

const filteredItems = computed(() => {
  let list = filterFeedback(items.value, {
    status: filters.status,
    courseId: filters.courseId,
    query: filters.query,
  })
  if (filters.time === 'week') {
    const cutoff = Date.now() - 7 * DAY
    list = list.filter((item) => {
      const t = item.graded_at ? new Date(item.graded_at).getTime() : null
      return t != null && !Number.isNaN(t) && t >= cutoff
    })
  }
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredItems.value.length / pageSize.value)))

const pageItems = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredItems.value.slice(start, start + pageSize.value)
})

function selectStatus(status) {
  filters.status = status
  page.value = 1
}

function onPageSizeChange() {
  page.value = 1
}

function go(route) {
  // 仅允许服务端返回的学生相对路由
  if (route === '/student' || route.startsWith('/student/')) {
    router.push(route)
  }
}

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : timeFmt.format(date)
}

onMounted(loadFeedback)
</script>

<template>
  <AppLayout>
    <div class="page">
      <!-- 页头 -->
      <header class="page-head">
        <div>
          <h1 class="page-title">提交与反馈</h1>
          <p class="page-sub">最近提交的作业、考试与实验反馈</p>
        </div>
      </header>

      <!-- 状态标签（白色分段卡） -->
      <div class="status-tabs" role="tablist" aria-label="反馈状态">
        <button
          v-for="tab in [
            { key: 'all', label: '全部' },
            { key: 'needs_revision', label: '需修改' },
            { key: 'passed', label: '已通过' },
            { key: 'pending', label: '等待评分' },
          ]"
          :key="tab.key"
          type="button"
          class="status-tab"
          :class="{ active: filters.status === tab.key }"
          role="tab"
          :aria-selected="filters.status === tab.key"
          @click="selectStatus(tab.key)"
        >
          {{ tab.label }}
          <span class="tab-count">{{ statusCounts[tab.key] }}</span>
        </button>
      </div>

      <!-- 筛选行 -->
      <div class="filter-row">
        <label class="filter-field">
          <span class="filter-label">课程</span>
          <select v-model="filters.courseId" class="filter-course" aria-label="按课程筛选" @change="page = 1">
            <option value="">全部课程</option>
            <option v-for="c in courseOptions" :key="c.id" :value="c.id">{{ c.title }}</option>
          </select>
        </label>
        <label class="filter-field">
          <span class="filter-label">时间</span>
          <select v-model="filters.time" class="filter-time" aria-label="按时间筛选" @change="page = 1">
            <option value="all">全部时间</option>
            <option value="week">近 7 天</option>
          </select>
        </label>
        <div class="search-box">
          <span class="search-icon" aria-hidden="true"><AppIcon name="search" :size="16" /></span>
          <input v-model="filters.query" type="search" class="search-input" placeholder="搜索标题或课程" aria-label="搜索反馈" />
        </div>
      </div>

      <!-- 计数行 -->
      <p class="result-count" v-if="!loading && !error">
        共 {{ filteredItems.length }} 条反馈
      </p>

      <!-- 列表 -->
      <DashboardAsyncState
        :loading="loading"
        :error="error"
        :empty="filteredItems.length === 0"
        empty-title="暂无反馈"
        empty-body="获得批改后，反馈会出现在这里"
        @retry="loadFeedback"
      >
        <div class="feedback-list">
          <article
            v-for="item in pageItems"
            :key="item.kind + '-' + item.id"
            class="feedback-row"
          >
            <span class="feedback-status-icon" :class="'status-' + statusTone[feedbackStatus(item)]" aria-hidden="true">
              <AppIcon :name="statusIcon[feedbackStatus(item)]" :size="18" />
            </span>
            <div class="feedback-main">
              <div class="feedback-head">
                <span class="feedback-title">{{ item.title }}</span>
                <span class="feedback-score" :class="'status-' + statusTone[feedbackStatus(item)]">
                  {{ item.score ?? '—' }}
                </span>
              </div>
              <span class="feedback-course">{{ item.course_title || '—' }} · {{ kindLabel[item.kind] || item.kind }}</span>
              <p class="feedback-summary">{{ item.feedback || '暂无文字反馈' }}</p>
              <span class="feedback-time">{{ formatTime(item.graded_at) }}</span>
            </div>
            <div class="feedback-right">
              <span class="feedback-pill" :class="'status-' + statusTone[feedbackStatus(item)]">
                {{ statusLabel[feedbackStatus(item)] }}
              </span>
              <button type="button" class="detail-link" @click="go(item.route)">
                查看详情
                <AppIcon name="arrow-right" :size="14" />
              </button>
            </div>
          </article>
        </div>

        <!-- 分页页脚：一页时也保持可见与连贯 -->
        <footer class="page-footer" v-if="!loading && !error">
          <span class="page-meta">
            第 <strong>{{ page }}</strong> / {{ totalPages }} 页
          </span>
          <label class="page-size-field">
            每页
            <select v-model="pageSize" class="page-size" aria-label="每页条数" @change="onPageSizeChange">
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option>
            </select>
            条
          </label>
          <div class="page-nav">
            <button type="button" class="prev-page" :disabled="page <= 1" @click="page--">上一页</button>
            <button type="button" class="next-page" :disabled="page >= totalPages" @click="page++">下一页</button>
          </div>
        </footer>
      </DashboardAsyncState>
    </div>
  </AppLayout>
</template>

<style scoped>
.page { display: flex; flex-direction: column; gap: 16px; }

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

/* ── 状态标签（白色分段卡） ───────────────────────────────────── */
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

/* ── 筛选行 ───────────────────────────────────────────────────── */
.filter-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  padding: 4px 0;
}
.filter-field { display: flex; flex-direction: column; gap: 4px; }
.filter-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  font-weight: 500;
}
.filter-field select {
  width: auto;
  min-width: 130px;
  padding: 7px 10px;
  font-size: var(--text-sm);
  border-radius: var(--radius-control);
}
.search-box {
  flex: 1;
  min-width: 220px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
}
.search-icon {
  display: inline-flex;
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.search-input {
  border: none;
  background: transparent;
  padding: 9px 0;
  font-size: var(--text-sm);
}
.search-input:focus { outline: none; box-shadow: none; border-color: transparent; }

.result-count {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

/* ── 反馈行（122–126px） ──────────────────────────────────────── */
.feedback-list { display: flex; flex-direction: column; gap: 12px; }
.feedback-row {
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 122px;
  padding: 18px 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}
.feedback-status-icon {
  flex-shrink: 0;
  width: 40px; height: 40px;
  border-radius: var(--radius-control);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.feedback-status-icon.status-warning { background: var(--warning-light); color: var(--warning); }
.feedback-status-icon.status-danger { background: var(--danger-light); color: var(--danger); }
.feedback-status-icon.status-success { background: var(--success-light); color: var(--success); }

.feedback-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.feedback-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}
.feedback-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
}
.feedback-score {
  font-size: var(--text-sm);
  font-weight: 700;
  flex-shrink: 0;
}
.feedback-score.status-warning { color: var(--warning); }
.feedback-score.status-danger { color: var(--danger); }
.feedback-score.status-success { color: var(--success); }
.feedback-course {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
.feedback-summary {
  margin: 2px 0 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.feedback-time {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.feedback-right {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}
.feedback-pill {
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: 600;
  white-space: nowrap;
}
.feedback-pill.status-warning { color: var(--warning); background: var(--warning-light); }
.feedback-pill.status-danger { color: var(--danger); background: var(--danger-light); }
.feedback-pill.status-success { color: var(--success); background: var(--success-light); }

.detail-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  padding: 0;
  color: var(--primary);
  font-size: var(--text-xs);
  font-weight: 600;
  cursor: pointer;
}
.detail-link:hover { color: var(--primary-dark); }

/* ── 分页页脚 ─────────────────────────────────────────────────── */
.page-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 14px 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
}
.page-meta {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.page-size-field {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.page-size {
  width: auto;
  padding: 5px 8px;
  font-size: var(--text-sm);
  border-radius: var(--radius-control);
}
.page-nav {
  display: flex;
  gap: 8px;
}
.page-nav button {
  padding: 6px 14px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-control);
  background: var(--surface);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  cursor: pointer;
}
.page-nav button:hover:not(:disabled) { background: var(--primary-light); color: var(--primary); }
.page-nav button:disabled { opacity: 0.4; cursor: not-allowed; }

@media (max-width: 767.98px) {
  .feedback-row { flex-wrap: wrap; }
  .feedback-right { flex-direction: row; align-items: center; width: 100%; justify-content: space-between; }
}
</style>
