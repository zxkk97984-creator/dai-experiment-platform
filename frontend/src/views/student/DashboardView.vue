<script setup>
// 学生首页（参考图 04）：
// 问候 → 全宽续学面板 → 四摘要卡 → 左列(待办任务|最新反馈) → 右列(学习概览|公告|我的课程)
// 全部数据来自 dashboardAPI.student() 与本地真实进度，零 mock、零样例数字。

import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppLayout from '../../components/layout/AppLayout.vue'
import AnnouncementPanel from '../../components/dashboard/AnnouncementPanel.vue'
import DashboardAsyncState from '../../components/dashboard/DashboardAsyncState.vue'
import AppIcon from '../../components/ui/AppIcon.vue'
import UiPanel from '../../components/ui/UiPanel.vue'
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
// 续学课程的真实进度（0–100），请求失败或非课程路由时为 null（不伪造）
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
const feedbackIcon = { pending: 'clock', needs_revision: 'close', passed: 'check' }
const feedbackLabel = { pending: '待评分', needs_revision: '需修改', passed: '已通过' }

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

/** 从服务端续学路由提取课程 id，拉服务端学习进度（TASK-018） */
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

onMounted(async () => {
  await loadDashboard()
  if (!error.value) await loadContinueProgress()
})
</script>

<template>
  <AppLayout>
    <div class="dash">
      <!-- 问候行 -->
      <header class="dash-greeting">
        <div>
          <h1 class="greeting-title">你好，{{ firstName }}</h1>
          <p class="greeting-date">{{ todayText }}</p>
          <p v-if="dashboard" class="student-identity">学号 {{ dashboard.student_no || auth.user?.student_no || '未设置' }} · {{ dashboard.teaching_classes?.join('、') || '未分配教学班' }}</p>
        </div>
      </header>

      <!-- 全宽续学面板 -->
      <section v-if="dashboard?.continue_learning" class="continue-panel">
        <div class="continue-info">
          <span class="continue-icon" aria-hidden="true">
            <AppIcon name="book" :size="24" />
          </span>
          <div class="continue-text">
            <span class="continue-label">继续学习</span>
            <span class="continue-title">{{ dashboard.continue_learning.title }}</span>
            <span class="continue-sub" v-if="dashboard.continue_learning.subtitle">
              {{ dashboard.continue_learning.subtitle }}
            </span>
          </div>
        </div>
        <div class="continue-progress">
          <template v-if="continueLoaded && continueProgress != null">
            <span class="continue-progress-text">已学 {{ continueProgress }}%</span>
            <UiProgress :value="continueProgress" />
          </template>
        </div>
        <button
          type="button"
          class="continue-btn"
          @click="go(dashboard.continue_learning.route)"
        >
          继续学习
          <AppIcon name="arrow-right" :size="16" />
        </button>
      </section>

      <!-- 四摘要卡 -->
      <section class="summary-cards" aria-label="学习概况">
        <div class="summary-card tone-course">
          <span class="summary-icon" aria-hidden="true"><AppIcon name="book" :size="20" /></span>
          <span class="summary-num">{{ dashboard?.summary?.course_count ?? '—' }}</span>
          <span class="summary-label">课程</span>
        </div>
        <div class="summary-card tone-pending">
          <span class="summary-icon" aria-hidden="true"><AppIcon name="assignment" :size="20" /></span>
          <span class="summary-num">{{ dashboard?.summary?.pending_assignment_count ?? '—' }}</span>
          <span class="summary-label">待交作业</span>
        </div>
        <div class="summary-card tone-exam">
          <span class="summary-icon" aria-hidden="true"><AppIcon name="exam" :size="20" /></span>
          <span class="summary-num">{{ dashboard?.summary?.upcoming_exam_count ?? '—' }}</span>
          <span class="summary-label">即将考试</span>
        </div>
        <div class="summary-card tone-announcement">
          <span class="summary-icon" aria-hidden="true"><AppIcon name="notification" :size="20" /></span>
          <span class="summary-num">{{ dashboard?.summary?.unread_announcement_count ?? '—' }}</span>
          <span class="summary-label">未读公告</span>
        </div>
      </section>

      <!-- 主双列 -->
      <div class="dash-grid">
        <div class="col-left">
          <!-- 待办任务 -->
          <UiPanel compact class="tasks-panel">
            <template #header><h2 class="panel-title">待办任务</h2></template>
            <DashboardAsyncState
              :loading="loading"
              :error="error"
              :empty="!dashboard?.priority_items?.length"
              empty-title="暂无待办"
              empty-body="当前没有待完成的作业或考试"
              @retry="loadDashboard"
            >
              <ul v-if="dashboard" class="task-list">
                <li
                  v-for="item in dashboard.priority_items.slice(0, 3)"
                  :key="item.kind + '-' + item.id"
                  class="task-row"
                >
                  <span class="task-urgency-dot" :class="'urgency-' + item.urgency" aria-hidden="true"></span>
                  <button type="button" class="task-main" @click="go(item.route)">
                    <span class="task-title">{{ item.title }}</span>
                    <span class="task-meta">
                      {{ kindLabel[item.kind] || item.kind }}
                      <template v-if="item.course_title"> · {{ item.course_title }}</template>
                      <template v-if="item.time_at"> · {{ formatTime(item.time_at) }}</template>
                    </span>
                  </button>
                  <span class="urgency-text" :class="'urgency-' + item.urgency">
                    {{ urgencyText[item.urgency] || '常规' }}
                  </span>
                </li>
              </ul>
            </DashboardAsyncState>
            <div class="view-all-row">
              <button type="button" class="view-all-btn" @click="router.push('/student/assignments')">
                查看全部任务
              </button>
            </div>
          </UiPanel>

          <!-- 最新反馈 -->
          <UiPanel compact class="feedback-panel">
            <template #header><h2 class="panel-title">最新反馈</h2></template>
            <DashboardAsyncState
              :loading="loading"
              :error="error"
              :empty="!dashboard?.recent_feedback?.length"
              empty-title="暂无反馈"
              empty-body="获得批改后，反馈会出现在这里"
              @retry="loadDashboard"
            >
              <ul v-if="dashboard" class="feedback-list">
                <li
                  v-for="item in dashboard.recent_feedback.slice(0, 3)"
                  :key="item.kind + '-' + item.id"
                  class="feedback-row"
                >
                  <span class="feedback-icon" :class="'status-' + feedbackStatus(item)" aria-hidden="true">
                    <AppIcon :name="feedbackIcon[feedbackStatus(item)]" :size="16" />
                  </span>
                  <button type="button" class="feedback-main" @click="go(item.route)">
                    <span class="feedback-head">
                      <span class="feedback-title">{{ item.title }}</span>
                      <span class="feedback-score" :class="'status-' + feedbackStatus(item)">
                        {{ item.score ?? '—' }}
                      </span>
                    </span>
                    <span class="feedback-summary">{{ item.feedback || '暂无文字反馈' }}</span>
                    <span class="feedback-meta">
                      {{ item.course_title }} · {{ formatTime(item.graded_at) }}
                    </span>
                  </button>
                  <span class="feedback-pill" :class="'status-' + feedbackStatus(item)">
                    {{ feedbackLabel[feedbackStatus(item)] }}
                  </span>
                </li>
              </ul>
            </DashboardAsyncState>
            <div class="view-all-row">
              <button type="button" class="view-all-btn" @click="router.push('/student/feedback')">
                查看全部反馈
              </button>
            </div>
          </UiPanel>
        </div>

        <div class="col-right">
          <!-- 学习概览 -->
          <UiPanel compact class="learning-panel">
            <template #header><h2 class="panel-title">学习概览</h2></template>
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
                  <span class="learning-meta" v-if="dashboard.continue_learning.updated_at">
                    最近更新 · {{ formatTime(dashboard.continue_learning.updated_at) }}
                  </span>
                </div>
                <template v-if="continueLoaded && continueProgress != null">
                  <div class="learning-progress">
                    <span class="learning-progress-text">已学 {{ continueProgress }}%</span>
                    <UiProgress :value="continueProgress" />
                  </div>
                </template>
                <div class="learning-stat">
                  已加入 <strong>{{ dashboard.summary?.course_count ?? 0 }}</strong> 门课程
                </div>
              </div>
            </DashboardAsyncState>
          </UiPanel>

          <!-- 通知公告 -->
          <UiPanel compact class="announcement-panel-wrap">
            <AnnouncementPanel
              :announcements="dashboard?.announcements || []"
              :loading="loading"
              :error="error"
              :can-publish="false"
              @retry="loadDashboard"
              @mark-read="markRead"
            />
          </UiPanel>

          <!-- 我的课程 -->
          <UiPanel compact class="courses-panel">
            <template #header><h2 class="panel-title">我的课程</h2></template>
            <DashboardAsyncState
              :loading="loading"
              :error="error"
              :empty="!dashboard?.courses?.length"
              empty-title="暂无课程"
              empty-body="加入课程后将在这里展示学习动态"
              @retry="loadDashboard"
            >
              <ul v-if="dashboard" class="course-list">
                <li v-for="course in dashboard.courses.slice(0, 3)" :key="course.id" class="course-row">
                  <button type="button" class="course-row-link" @click="go(course.route)">
                    {{ course.title }}
                  </button>
                  <span class="course-row-meta">
                    {{ course.academic_term || '未设置学期' }} · {{ course.teaching_classes?.join('、') || '未设置教学班' }} · {{ course.pending_assignment_count }} 份待交
                  </span>
                </li>
              </ul>
            </DashboardAsyncState>
            <div class="view-all-row">
              <button type="button" class="view-all-btn" @click="router.push('/student/courses')">
                查看全部课程
              </button>
            </div>
          </UiPanel>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.dash { display: flex; flex-direction: column; gap: 20px; }

/* ── 问候行 ─────────────────────────────────────────────────── */
.dash-greeting { padding: 2px 0; }
.greeting-title {
  margin: 0;
  font-size: 30px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.02em;
  line-height: 1.2;
}
.greeting-date {
  margin: 6px 0 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.student-identity{margin:6px 0 0;color:var(--text-secondary);font-size:13px}

/* ── 续学面板（132–136px 高） ───────────────────────────────── */
.continue-panel {
  display: flex;
  align-items: center;
  gap: 24px;
  height: 134px;
  padding: 0 24px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}

.continue-info {
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 1.2;
  min-width: 0;
}
.continue-icon {
  width: 48px; height: 48px;
  border-radius: var(--radius-control);
  background: var(--primary-light);
  color: var(--primary);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.continue-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.continue-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  font-weight: 500;
}
.continue-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.continue-sub {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.continue-progress {
  flex: 0.9;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.continue-progress-text {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
}

.continue-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 44px;
  padding: 0 24px;
  min-width: 138px;
  justify-content: center;
  border: none;
  border-radius: var(--radius-control);
  background: var(--primary);
  color: var(--surface);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
}
.continue-btn:hover { background: var(--primary-dark); }

/* ── 四摘要卡（82–88px 高） ─────────────────────────────────── */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.summary-card {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 86px;
  padding: 0 18px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}
.summary-icon {
  width: 42px; height: 42px;
  border-radius: var(--radius-control);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.tone-course .summary-icon { background: var(--primary-light); color: var(--primary); }
.tone-pending .summary-icon { background: var(--warning-light); color: var(--warning); }
.tone-exam .summary-icon { background: var(--success-light); color: var(--success); }
.tone-announcement .summary-icon { background: var(--purple-light); color: var(--purple); }

.summary-num {
  font-size: 24px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1;
}
.summary-label {
  margin-top: 3px;
  font-size: var(--text-xs);
  color: var(--text-secondary);
}
.summary-card > .summary-num + .summary-label,
.summary-card .summary-label { align-self: center; }

/* ── 主双列（1.1fr / 0.9fr） ────────────────────────────────── */
.dash-grid {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 20px;
  align-items: start;
}
.col-left, .col-right {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.panel-title {
  margin: 0;
  font-size: var(--text-base);
  font-weight: 700;
  color: var(--ink);
}

/* ── 紧凑行（44–56px） ─────────────────────────────────────── */
.task-list, .feedback-list, .course-list { list-style: none; margin: 0; padding: 0; }

.task-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 52px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}
.task-row:last-child { border-bottom: none; }

.task-urgency-dot {
  flex-shrink: 0;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--text-tertiary);
}
.task-urgency-dot.urgency-urgent { background: var(--danger); }
.task-urgency-dot.urgency-soon { background: var(--warning); }

.task-main {
  flex: 1;
  min-width: 0;
  text-align: left;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.task-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
}
.task-main:hover .task-title { color: var(--primary); }
.task-meta {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.urgency-text {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-control);
  color: var(--text-secondary);
  background: var(--surface-raised);
}
.urgency-text.urgency-urgent { color: var(--danger); background: var(--danger-light); }
.urgency-text.urgency-soon { color: var(--warning); background: var(--warning-light); }

/* ── 反馈行 ─────────────────────────────────────────────────── */
.feedback-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 56px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}
.feedback-row:last-child { border-bottom: none; }

.feedback-icon {
  flex-shrink: 0;
  width: 30px; height: 30px;
  border-radius: var(--radius-control);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary);
  background: var(--surface-raised);
}
.feedback-icon.status-pending { color: var(--warning); background: var(--warning-light); }
.feedback-icon.status-needs_revision { color: var(--danger); background: var(--danger-light); }
.feedback-icon.status-passed { color: var(--success); background: var(--success-light); }

.feedback-main {
  flex: 1;
  min-width: 0;
  text-align: left;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.feedback-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.feedback-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
}
.feedback-main:hover .feedback-title { color: var(--primary); }
.feedback-score {
  font-size: var(--text-xs);
  font-weight: 700;
  flex-shrink: 0;
}
.feedback-score.status-pending { color: var(--warning); }
.feedback-score.status-needs_revision { color: var(--danger); }
.feedback-score.status-passed { color: var(--success); }

.feedback-summary {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.feedback-meta {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.feedback-pill {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-control);
  color: var(--text-secondary);
  background: var(--surface-raised);
}
.feedback-pill.status-pending { color: var(--warning); background: var(--warning-light); }
.feedback-pill.status-needs_revision { color: var(--danger); background: var(--danger-light); }
.feedback-pill.status-passed { color: var(--success); background: var(--success-light); }

/* ── 学习概览 ───────────────────────────────────────────────── */
.learning-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.learning-course {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.learning-course-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
}
.learning-meta {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
.learning-progress {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.learning-progress-text {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-secondary);
}
.learning-stat {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

/* ── 我的课程 ───────────────────────────────────────────────── */
.course-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 48px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}
.course-row:last-child { border-bottom: none; }
.course-row-link {
  background: none;
  border: none;
  padding: 0;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
  cursor: pointer;
  text-align: left;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.course-row-link:hover { color: var(--primary); }
.course-row-meta {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  flex-shrink: 0;
}

/* ── 查看全部 ───────────────────────────────────────────────── */
.view-all-row {
  border-top: 1px solid var(--border);
  margin-top: 10px;
  padding-top: 10px;
  text-align: center;
}
.view-all-btn {
  background: none;
  border: none;
  padding: 4px 8px;
  color: var(--primary);
  font-size: var(--text-xs);
  font-weight: 600;
  cursor: pointer;
}
.view-all-btn:hover { color: var(--primary-dark); }

/* ── 响应式 ─────────────────────────────────────────────────── */
@media (max-width: 1199px) {
  .dash-grid { grid-template-columns: 1fr; }
  .summary-cards { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 767.98px) {
  .dash { gap: 16px; }
  .greeting-title { font-size: 24px; }
  .continue-panel { flex-wrap: wrap; height: auto; padding: 16px; gap: 12px; }
  .continue-info { flex: 1 1 100%; }
  .continue-btn { width: 100%; }
  .summary-cards { grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .summary-card { height: 74px; padding: 0 12px; }
}
</style>
