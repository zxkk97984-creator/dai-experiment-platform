<script setup>
// 教师工作台（V3）：问候页头 + 指标条 + 聚合待处理工作/公告 + 课程概览 + 最近提交表格。
// 数据仍由一次 /dashboard/teacher 聚合请求驱动；工作队列按任务聚合，最近提交为跨实体混合表格。

import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppLayout from '../../components/layout/AppLayout.vue'
import AnnouncementComposer from '../../components/dashboard/AnnouncementComposer.vue'
import AnnouncementPanel from '../../components/dashboard/AnnouncementPanel.vue'
import DashboardAsyncState from '../../components/dashboard/DashboardAsyncState.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import { announcementsAPI } from '../../api/announcements.js'
import { dashboardAPI } from '../../api/dashboard.js'
import { useAuthStore } from '../../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()

const loading = ref(true)
const error = ref(false)
const dashboard = ref(null)
const showComposer = ref(false)
const panelRef = ref(null)
const announcementSection = ref(null)

const teacherName = (auth.user?.real_name || auth.user?.username || '老师').slice(0, 8)

const todayText = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  weekday: 'long',
}).format(new Date())

const timeFmt = new Intl.DateTimeFormat('zh-CN', {
  month: 'numeric',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

const workStatusMap = {
  pending_grading: { label: '待评分', tone: 'badge-warning' },
  review_required: { label: '待复核', tone: 'badge-info' },
  pending_release: { label: '待发布', tone: 'badge-neutral' },
  graded: { label: '已评分', tone: 'badge-success' },
  failed: { label: '失败', tone: 'badge-danger' },
}

function workStatus(item) {
  return workStatusMap[item.status] || { label: item.detail || '待处理', tone: 'badge-neutral' }
}

async function loadDashboard() {
  loading.value = true
  error.value = false
  try {
    const { data } = await dashboardAPI.teacher()
    dashboard.value = data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function go(route) {
  if (route === '/teacher' || route.startsWith('/teacher/')) {
    router.push(route)
  }
}

function scrollToAnnouncements() {
  announcementSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : timeFmt.format(date)
}

function primaryWork() {
  return dashboard.value?.work_items?.[0] || null
}

function primaryActionRoute() {
  const first = primaryWork()
  if (first) return first.route
  if (dashboard.value?.summary?.pending_review_count) return '/teacher/submissions'
  return '/teacher/courses'
}

const primaryActionLabel = computed(() => {
  const summary = dashboard.value?.summary
  if (summary?.pending_grading_count > 0) return `处理待评分 ${summary.pending_grading_count}`
  if (summary?.pending_review_count > 0) return `处理待复核 ${summary.pending_review_count}`
  return primaryWork() ? '处理工作' : '管理课程'
})

const leadText = computed(() => {
  const s = dashboard.value?.summary
  if (!s) return '加载工作概况中…'
  const parts = []
  if (s.pending_grading_count) parts.push(`${s.pending_grading_count} 份提交待评分`)
  if (s.pending_review_count) parts.push(`${s.pending_review_count} 份 AI 评分待复核`)
  if (s.pending_release_count) parts.push(`${s.pending_release_count} 场考试待发布成绩`)
  if (s.upcoming_deadline_count) parts.push(`${s.upcoming_deadline_count} 项任务临近截止`)
  return parts.length ? `${parts.join('、')}。优先处理评分工作。` : '暂无待处理工作，可以先查看课程公告。'
})

function submissionStatus(row) {
  return workStatusMap[row.status] || { label: row.status || '—', tone: 'badge-neutral' }
}

function submissionScore(row) {
  if (row.ai_score != null) return Number(row.ai_score).toFixed(1)
  if (row.score != null) return Number(row.score).toFixed(1)
  return '—'
}

function testsText(row) {
  if (row.tests_total == null) return '—'
  return `${row.tests_passed ?? 0} / ${row.tests_total}`
}

async function markRead(notice) {
  try {
    await announcementsAPI.markRead(notice.id)
    if (!dashboard.value) return
    dashboard.value = {
      ...dashboard.value,
      announcements: dashboard.value.announcements.map((a) =>
        a.id === notice.id ? { ...a, is_read: true } : a,
      ),
    }
  } catch {
    // 标记失败保持原状，下次操作可重试
  }
}

function onPublished() {
  showComposer.value = false
  loadDashboard()
  nextTick(() => {
    panelRef.value?.$el?.querySelector('.publish-btn')?.focus() || document.querySelector('.publish-btn')?.focus()
  })
}

function onCloseComposer() {
  showComposer.value = false
  nextTick(() => {
    panelRef.value?.$el?.querySelector('.publish-btn')?.focus() || document.querySelector('.publish-btn')?.focus()
  })
}

onMounted(loadDashboard)
</script>

<template>
  <AppLayout>
    <div class="dash">
      <section class="page-head">
        <div class="ph-title">
          <p class="eyebrow">{{ todayText }}</p>
          <h1>你好，{{ teacherName }}</h1>
          <p class="lead">{{ leadText }}</p>
        </div>
        <div class="ph-actions">
          <button type="button" class="btn btn-secondary" @click="scrollToAnnouncements">查看公告</button>
          <button type="button" class="btn btn-primary btn-lg work-queue-btn" @click="go(primaryActionRoute())">
            {{ primaryActionLabel }}
            <AppIcon name="arrow-right" :size="15" />
          </button>
        </div>
      </section>

      <section class="metric-strip" aria-label="工作概况">
        <div class="metric"><span class="m-value">{{ dashboard?.summary?.active_course_count ?? dashboard?.summary?.course_count ?? '—' }}</span><span class="m-label">进行中课程</span></div>
        <div class="metric"><span class="m-value">{{ dashboard?.summary?.student_count ?? '—' }}</span><span class="m-label">在册学生</span></div>
        <div class="metric em"><span class="m-value">{{ dashboard?.summary?.pending_grading_count ?? '—' }}</span><span class="m-label">待评分提交</span></div>
        <div class="metric warn"><span class="m-value">{{ dashboard?.summary?.upcoming_deadline_count ?? '—' }}</span><span class="m-label">近 7 天截止</span></div>
      </section>

      <div class="grid-2-1">
        <section class="panel">
          <div class="panel-head">
            <div class="ph-label"><p class="eyebrow">Work queue</p><h3>待处理工作</h3></div>
            <button type="button" class="btn btn-ghost btn-sm" @click="go('/teacher/submissions/unified')">全部 →</button>
          </div>
          <div class="panel-body work-queue-body">
            <DashboardAsyncState
              :loading="loading"
              :error="error"
              :empty="!dashboard?.work_items?.length"
              empty-title="暂无待处理工作"
              empty-body="当前没有需要复核或即将截止的任务"
              @retry="loadDashboard"
            >
              <div v-if="dashboard" class="work-list">
                <button
                  v-for="item in dashboard.work_items"
                  :key="item.kind + '-' + item.id"
                  type="button"
                  class="work-row"
                  @click="go(item.route)"
                >
                  <span class="urgency-dot" :class="'urgency-' + item.urgency" aria-hidden="true"></span>
                  <span class="wr-main">
                    <span class="wr-title">{{ item.title }}</span>
                    <span class="wr-meta">
                      {{ item.course_title }}
                      <template v-if="item.time_at"> · {{ formatTime(item.time_at) }}</template>
                    </span>
                  </span>
                  <span v-if="workStatus(item).label" class="badge" :class="workStatus(item).tone">
                    <span class="dot"></span>{{ workStatus(item).label }}
                  </span>
                </button>
              </div>
            </DashboardAsyncState>
          </div>
        </section>

        <section ref="announcementSection" class="panel">
          <div class="panel-head">
            <div class="ph-label"><p class="eyebrow">Announcements</p><h3>课程公告</h3></div>
            <button
              v-if="!showComposer"
              type="button"
              class="btn btn-ghost btn-sm btn-icon publish-btn"
              aria-label="发布公告"
              @click="showComposer = true"
            >
              <AppIcon name="plus" :size="15" />
            </button>
          </div>
          <div class="panel-body">
            <AnnouncementPanel
              ref="panelRef"
              :announcements="dashboard?.announcements || []"
              :loading="loading"
              :error="error"
              :can-publish="false"
              @retry="loadDashboard"
              @publish="showComposer = true"
              @mark-read="markRead"
            />
          </div>
        </section>
      </div>

      <section class="panel">
        <div class="panel-head">
          <div class="ph-label"><p class="eyebrow">Course health</p><h3>课程概览</h3></div>
        </div>
        <div class="panel-body">
          <DashboardAsyncState
            :loading="loading"
            :error="error"
            :empty="!dashboard?.course_health?.length"
            empty-title="暂无课程"
            empty-body="创建课程后，健康度会展示在这里"
            @retry="loadDashboard"
          >
            <div v-if="dashboard" class="health-list">
              <button
                v-for="row in dashboard.course_health"
                :key="row.course_id"
                type="button"
                class="health-row health-link"
                @click="go(row.route)"
              >
                <span class="health-title">{{ row.title }}</span>
                <span class="health-meta">
                  {{ row.student_count }} 名学生
                  <template v-if="row.pending_review_count"> · {{ row.pending_review_count }} 项待复核</template>
                  <template v-if="row.upcoming_deadline_count"> · {{ row.upcoming_deadline_count }} 项即将截止</template>
                  ·
                  <template v-if="row.at_risk_expected_count">
                    {{ row.at_risk_submitted_count ?? 0 }}/{{ row.at_risk_expected_count }} 已提交
                  </template>
                  <template v-else>—</template>
                </span>
              </button>
            </div>
          </DashboardAsyncState>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div class="ph-label"><p class="eyebrow">Recent</p><h3>最近提交</h3></div>
          <button type="button" class="btn btn-ghost btn-sm" @click="go('/teacher/submissions/unified')">查看全部 →</button>
        </div>
        <div class="panel-body recent-body">
          <DashboardAsyncState
            :loading="loading"
            :error="error"
            :empty="!dashboard?.recent_submissions?.length"
            empty-title="暂无提交"
            empty-body="学生提交实验或作业后，记录会出现在这里"
            @retry="loadDashboard"
          >
            <div v-if="dashboard" class="table-scroll">
              <table class="ds-table recent-table">
                <thead>
                  <tr>
                    <th>学生</th>
                    <th>实验 / 作业</th>
                    <th>状态</th>
                    <th class="cell-num">测试</th>
                    <th class="cell-num">AI 得分</th>
                    <th>提交时间</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in dashboard.recent_submissions" :key="row.kind + '-' + row.id">
                    <td>
                      <button type="button" class="cell-main recent-link" @click="go(row.route)">
                        {{ row.student_name || '未命名学生' }}
                      </button>
                      <div class="cell-sub">{{ row.student_no || '—' }}</div>
                    </td>
                    <td>
                      <button type="button" class="recent-entry" @click="go(row.route)">{{ row.entry_title || '未命名任务' }}</button>
                      <div class="cell-sub">{{ row.course_title || '—' }}</div>
                    </td>
                    <td>
                      <span class="badge" :class="submissionStatus(row).tone">
                        <span class="dot"></span>{{ submissionStatus(row).label }}
                      </span>
                    </td>
                    <td class="cell-num">{{ testsText(row) }}</td>
                    <td class="cell-num score-cell">{{ submissionScore(row) }}</td>
                    <td class="meta">{{ formatTime(row.submitted_at) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </DashboardAsyncState>
        </div>
      </section>

      <AnnouncementComposer
        v-if="showComposer"
        :courses="dashboard?.managed_courses || []"
        @close="onCloseComposer"
        @published="onPublished"
      />
    </div>
  </AppLayout>
</template>

<style scoped>
.dash { display: flex; flex-direction: column; gap: var(--space-5); }

.work-queue-body, .recent-body { padding: 4px 0; }
.work-list { display: flex; flex-direction: column; }
.work-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  background: transparent;
  border-top: 0;
  border-left: 0;
  border-right: 0;
  border-radius: 0;
  text-align: left;
}
.work-row:last-child { border-bottom: 0; }
.work-row:hover { background: var(--surface-sunken); border-color: var(--border); }
.urgency-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; background: var(--muted); }
.urgency-dot.urgency-urgent { background: var(--danger); }
.urgency-dot.urgency-soon { background: var(--warning); }
.wr-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.wr-title { font-size: var(--text-md); font-weight: 500; color: var(--fg); }
.wr-meta { font-size: var(--text-sm); color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.health-list { display: flex; flex-direction: column; }
.health-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
  background: transparent;
  border-top: 0;
  border-left: 0;
  border-right: 0;
  border-radius: 0;
  text-align: left;
}
.health-row:last-child { border-bottom: 0; }
.health-title { font-size: var(--text-md); font-weight: 500; color: var(--fg); }
.health-row:hover .health-title { color: var(--accent); }
.health-meta { font-size: var(--text-sm); color: var(--muted); flex-shrink: 0; }

.recent-link, .recent-entry {
  display: block;
  max-width: 220px;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.recent-link { font-weight: 600; color: var(--fg); }
.recent-entry { color: var(--fg); }
.recent-link:hover, .recent-entry:hover { color: var(--accent); background: transparent; }
.score-cell { font-weight: 600; }

@media (max-width: 1024px) {
  .grid-2-1 { grid-template-columns: 1fr; }
}
</style>
