<script setup>
// 学生首页（V2）：
// 页头问候 → 续学面板 → 指标条 → 左列（待办任务/最新反馈）→ 右列（学习概览/公告/课程）。
// 全部数据来自 dashboardAPI.student() 与真实学习进度，零 mock。

import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppLayout from '../../components/layout/AppLayout.vue'
import AnnouncementPanel from '../../components/dashboard/AnnouncementPanel.vue'
import DashboardAsyncState from '../../components/dashboard/DashboardAsyncState.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import UiProgress from '../../components/ui/UiProgress.vue'
import { announcementsAPI } from '../../api/announcements.js'
import { progressAPI } from '../../api/progress.js'
import { dashboardAPI } from '../../api/dashboard.js'
import { useAuthStore } from '../../stores/auth.js'
import { feedbackStatus } from '../../utils/studentUi.js'

const auth = useAuthStore()
const router = useRouter()

const loading = ref(true)
const error = ref(false)
const dashboard = ref(null)
const continueProgress = ref(null)
const continueLoaded = ref(false)

const firstName = (auth.user?.real_name || auth.user?.username || '同学').slice(0, 6)

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

const urgencyText = { urgent: '紧急', soon: '即将', normal: '常规' }
const kindLabel = { assignment: '作业', exam: '考试', experiment: '实验' }
const feedbackLabel = { pending: '待评分', needs_revision: '需修改', passed: '已通过' }
const feedbackTone = { pending: 'warning', needs_revision: 'danger', passed: 'success' }

function courseMeta(course) {
  const term = course.academic_term || ''
  const classes = (course.teaching_classes || []).filter((name) => name && name !== term)
  const parts = [term || '未设置学期']
  if (classes.length) parts.push(classes.join('、'))
  else if (!term) parts.push('未设置教学班')
  parts.push(`${course.pending_assignment_count ?? 0} 份待交`)
  return parts.join(' · ')
}

async function loadDashboard() {
  loading.value = true
  error.value = false
  try {
    const { data } = await dashboardAPI.student()
    dashboard.value = data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

async function loadContinueProgress() {
  continueLoaded.value = false
  continueProgress.value = null
  const route = dashboard.value?.continue_learning?.route || ''
  const m = route.match(/^\/student\/courses\/(\d+)(?:\/|$)/)
  if (!m) {
    continueLoaded.value = true
    return
  }
  const courseId = Number(m[1])
  try {
    const res = await progressAPI.getCourse(courseId)
    continueProgress.value = res.data.percent ?? 0
  } catch { /* 失败保持 null，不伪造 */ }
  continueLoaded.value = true
}

async function markRead(notice) {
  try {
    await announcementsAPI.markRead(notice.id)
    if (!dashboard.value) return
    const wasUnread = dashboard.value.announcements.some(
      (a) => a.id === notice.id && !a.is_read,
    )
    dashboard.value = {
      ...dashboard.value,
      announcements: dashboard.value.announcements.map((a) =>
        a.id === notice.id ? { ...a, is_read: true } : a,
      ),
      summary: {
        ...dashboard.value.summary,
        unread_announcement_count: Math.max(
          0,
          (dashboard.value.summary?.unread_announcement_count ?? 0) - (wasUnread ? 1 : 0),
        ),
      },
    }
  } catch {
    // 标记失败保持原状，下次操作可重试
  }
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

onMounted(async () => {
  await loadDashboard()
  if (!error.value) await loadContinueProgress()
})
</script>

<template>
  <AppLayout>
    <div class="dash">
      <section class="page-head dash-greeting">
        <div class="ph-title">
          <p class="eyebrow greeting-date">{{ todayText }}</p>
          <h1 class="greeting-title">你好，{{ firstName }}</h1>
          <p class="lead">
            学号 {{ dashboard?.student_no || auth.user?.student_no || '未设置' }}
            · {{ dashboard?.teaching_classes?.join('、') || '未分配教学班' }}
          </p>
        </div>
      </section>

      <section v-if="dashboard?.continue_learning" class="panel continue-panel">
        <div class="panel-body continue-body">
          <div class="continue-info">
            <span class="empty-mark continue-icon" aria-hidden="true">
              <AppIcon name="book" :size="20" />
            </span>
            <div class="continue-text">
              <span class="eyebrow">继续学习</span>
              <span class="continue-title">{{ dashboard.continue_learning.title }}</span>
              <span v-if="dashboard.continue_learning.subtitle" class="continue-sub">
                {{ dashboard.continue_learning.subtitle }}
              </span>
            </div>
          </div>
          <div v-if="continueLoaded && continueProgress != null" class="continue-progress">
            <span class="meta">已学 {{ continueProgress }}%</span>
            <UiProgress :value="continueProgress" />
          </div>
          <button
            type="button"
            class="btn btn-primary btn-lg continue-btn"
            @click="go(dashboard.continue_learning.route)"
          >
            继续学习
            <AppIcon name="arrow-right" :size="15" />
          </button>
        </div>
      </section>

      <section class="metric-strip summary-cards" aria-label="学习概况">
        <div class="metric summary-card"><span class="m-value summary-num">{{ dashboard?.summary?.course_count ?? '—' }}</span><span class="m-label summary-label">课程</span></div>
        <div class="metric summary-card"><span class="m-value summary-num">{{ dashboard?.summary?.pending_assignment_count ?? '—' }}</span><span class="m-label summary-label">待交作业</span></div>
        <div class="metric summary-card"><span class="m-value summary-num">{{ dashboard?.summary?.upcoming_exam_count ?? '—' }}</span><span class="m-label summary-label">即将考试</span></div>
        <div class="metric em summary-card"><span class="m-value summary-num">{{ dashboard?.summary?.unread_announcement_count ?? '—' }}</span><span class="m-label summary-label">未读公告</span></div>
      </section>

      <div class="grid-2-1 dash-grid">
        <div class="dash-col col-left">
          <section class="panel tasks-panel">
            <div class="panel-head">
              <div class="ph-label"><p class="eyebrow">Tasks</p><h3>待办任务</h3></div>
              <button type="button" class="btn btn-ghost btn-sm view-all-btn" @click="router.push('/student/assignments')">全部 →</button>
            </div>
            <div class="panel-body panel-list-body">
              <DashboardAsyncState
                :loading="loading"
                :error="error"
                :empty="!dashboard?.priority_items?.length"
                empty-title="暂无待办"
                empty-body="当前没有待完成的作业或考试"
                @retry="loadDashboard"
              >
                <div v-if="dashboard" class="task-list">
                  <button
                    v-for="item in dashboard.priority_items.slice(0, 3)"
                    :key="item.kind + '-' + item.id"
                    type="button"
                    class="work-row task-row"
                    @click="go(item.route)"
                  >
                    <span class="urgency-dot" :class="'urgency-' + item.urgency" aria-hidden="true"></span>
                    <span class="wr-main">
                      <span class="wr-title">{{ item.title }}</span>
                      <span class="wr-meta">
                        {{ kindLabel[item.kind] || item.kind }}
                        <template v-if="item.course_title"> · {{ item.course_title }}</template>
                        <template v-if="item.time_at"> · {{ formatTime(item.time_at) }}</template>
                      </span>
                    </span>
                    <span class="badge" :class="item.urgency === 'urgent' ? 'badge-danger' : item.urgency === 'soon' ? 'badge-warning' : 'badge-neutral'">
                      <span class="dot"></span>{{ urgencyText[item.urgency] || '常规' }}
                    </span>
                  </button>
                </div>
              </DashboardAsyncState>
            </div>
          </section>

          <section class="panel feedback-panel">
            <div class="panel-head">
              <div class="ph-label"><p class="eyebrow">Feedback</p><h3>最新反馈</h3></div>
              <button type="button" class="btn btn-ghost btn-sm view-all-btn" @click="router.push('/student/feedback')">全部 →</button>
            </div>
            <div class="panel-body panel-list-body">
              <DashboardAsyncState
                :loading="loading"
                :error="error"
                :empty="!dashboard?.recent_feedback?.length"
                empty-title="暂无反馈"
                empty-body="获得批改后，反馈会出现在这里"
                @retry="loadDashboard"
              >
                <div v-if="dashboard" class="feedback-list">
                  <button
                    v-for="item in dashboard.recent_feedback.slice(0, 3)"
                    :key="item.kind + '-' + item.id"
                    type="button"
                    class="work-row feedback-row"
                    @click="go(item.route)"
                  >
                    <span class="feedback-icon" :class="'status-' + feedbackStatus(item)" aria-hidden="true">
                      <AppIcon :name="feedbackStatus(item) === 'pending' ? 'clock' : feedbackStatus(item) === 'passed' ? 'check' : 'close'" :size="15" />
                    </span>
                    <span class="wr-main">
                      <span class="wr-title">
                        {{ item.title }}
                        <span class="num feedback-score" :class="'status-' + feedbackStatus(item)">{{ item.score ?? '—' }}</span>
                      </span>
                      <span class="wr-meta">{{ item.feedback || '暂无文字反馈' }}</span>
                      <span class="wr-meta">{{ item.course_title }} · {{ formatTime(item.graded_at) }}</span>
                    </span>
                    <span class="badge" :class="`badge-${feedbackTone[feedbackStatus(item)]}`"><span class="dot"></span>{{ feedbackLabel[feedbackStatus(item)] }}</span>
                  </button>
                </div>
              </DashboardAsyncState>
            </div>
          </section>
        </div>

        <div class="dash-col col-right">
          <section class="panel learning-panel">
            <div class="panel-head">
              <div class="ph-label"><p class="eyebrow">Overview</p><h3>学习概览</h3></div>
            </div>
            <div class="panel-body">
              <DashboardAsyncState
                :loading="loading"
                :error="error"
                :empty="!dashboard?.continue_learning"
                empty-title="暂无学习记录"
                empty-body="开始学习后，进度会显示在这里"
                @retry="loadDashboard"
              >
                <div v-if="dashboard?.continue_learning" class="learning-body">
                  <div class="learning-course">
                    <span class="learning-course-title">{{ dashboard.continue_learning.title }}</span>
                    <span v-if="dashboard.continue_learning.updated_at" class="learning-meta">最近更新 · {{ formatTime(dashboard.continue_learning.updated_at) }}</span>
                  </div>
                  <template v-if="continueLoaded && continueProgress != null">
                    <div class="learning-progress">
                      <span class="meta">已学 {{ continueProgress }}%</span>
                      <UiProgress :value="continueProgress" />
                    </div>
                  </template>
                  <div class="learning-stat">已加入 <strong>{{ dashboard.summary?.course_count ?? 0 }}</strong> 门课程</div>
                </div>
              </DashboardAsyncState>
            </div>
          </section>

          <section class="panel announcement-panel-wrap">
            <div class="panel-head">
              <div class="ph-label"><p class="eyebrow">Announcements</p><h3>通知公告</h3></div>
            </div>
            <div class="panel-body">
              <AnnouncementPanel
                :announcements="dashboard?.announcements || []"
                :loading="loading"
                :error="error"
                :can-publish="false"
                @retry="loadDashboard"
                @mark-read="markRead"
              />
            </div>
          </section>

          <section class="panel courses-panel">
            <div class="panel-head">
              <div class="ph-label"><p class="eyebrow">Courses</p><h3>我的课程</h3></div>
              <button type="button" class="btn btn-ghost btn-sm view-all-btn" @click="router.push('/student/courses')">全部 →</button>
            </div>
            <div class="panel-body panel-list-body">
              <DashboardAsyncState
                :loading="loading"
                :error="error"
                :empty="!dashboard?.courses?.length"
                empty-title="暂无课程"
                empty-body="加入课程后将在这里展示学习动态"
                @retry="loadDashboard"
              >
                <div v-if="dashboard" class="course-list">
                  <button
                    v-for="course in dashboard.courses.slice(0, 3)"
                    :key="course.id"
                    type="button"
                    class="course-row-link"
                    @click="go(course.route)"
                  >
                    <span class="course-row-title">{{ course.title }}</span>
                    <span class="course-row-meta">{{ courseMeta(course) }}</span>
                  </button>
                </div>
              </DashboardAsyncState>
            </div>
          </section>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.dash { display: flex; flex-direction: column; gap: var(--space-4); }
.dash-col { display: flex; flex-direction: column; gap: var(--space-3); min-width: 0; }
.dash-grid { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--space-3); }

/* 续学面板 */
.continue-body { display: flex; align-items: center; gap: var(--space-6); }
.continue-info { flex: 1; display: flex; align-items: center; gap: var(--space-3); min-width: 0; }
.continue-icon { flex-shrink: 0; }
.continue-text { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.continue-title { font-size: var(--text-xl); font-weight: 600; color: var(--fg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.continue-sub { font-size: var(--text-sm); color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.continue-progress { flex: 0 0 220px; display: flex; flex-direction: column; gap: 6px; }

/* 列表行：沿用 V2 work-row 语义，行点击整行可导航 */
.panel-list-body { padding: 4px 0; }
.task-list, .feedback-list, .course-list { display: flex; flex-direction: column; }
.work-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 16px;
  border: 0;
  border-bottom: 1px solid var(--border);
  border-radius: 0;
  background: transparent;
  text-align: left;
}
.work-row:last-child { border-bottom: 0; }
.work-row:hover { background: var(--surface-sunken); }
.urgency-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; background: var(--muted); }
.urgency-dot.urgency-urgent { background: var(--danger); }
.urgency-dot.urgency-soon { background: var(--warning); }
.wr-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.wr-title { display: flex; align-items: baseline; gap: 8px; font-size: var(--text-md); font-weight: 500; color: var(--fg); }
.wr-meta { font-size: var(--text-sm); color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.feedback-icon {
  width: 28px; height: 28px; flex: none; border-radius: var(--radius-md);
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--faint); background: var(--surface-subtle);
}
.feedback-icon.status-pending { color: var(--warning); background: var(--warning-bg); }
.feedback-icon.status-needs_revision { color: var(--danger); background: var(--danger-bg); }
.feedback-icon.status-passed { color: var(--success); background: var(--success-bg); }
.feedback-score { font-size: var(--text-sm); color: var(--muted); }
.feedback-score.status-pending { color: var(--warning); }
.feedback-score.status-needs_revision { color: var(--danger); }
.feedback-score.status-passed { color: var(--success); }

.learning-body { display: flex; flex-direction: column; gap: 12px; }
.learning-course { display: flex; flex-direction: column; gap: 2px; }
.learning-course-title { font-size: var(--text-md); font-weight: 600; color: var(--fg); }
.learning-meta { font-size: var(--text-xs); color: var(--faint); }
.learning-progress { display: flex; flex-direction: column; gap: 6px; }
.learning-stat { font-size: var(--text-base); color: var(--muted); }

.course-row-link {
  display: flex; flex-direction: column; gap: 3px;
  width: 100%; padding: 11px 16px; border: 0; border-bottom: 1px solid var(--border);
  border-radius: 0; background: transparent; text-align: left;
}
.course-row-link:last-child { border-bottom: 0; }
.course-row-link:hover { background: var(--surface-sunken); }
.course-row-title { font-size: var(--text-md); font-weight: 500; color: var(--fg); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.course-row-link:hover .course-row-title { color: var(--accent); }
.course-row-meta { font-size: var(--text-sm); color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

@media (max-width: 1024px) {
  .dash-grid { grid-template-columns: 1fr; }
}
@media (max-width: 820px) {
  .continue-body { flex-wrap: wrap; }
  .continue-progress { flex: 1 1 100%; }
}
</style>
