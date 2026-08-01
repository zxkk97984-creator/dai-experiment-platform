<script setup>
// 学生首页：一次聚合请求渲染真实数据；任务优先，公告为辅助列

import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppLayout from '../../components/layout/AppLayout.vue'
import AnnouncementPanel from '../../components/dashboard/AnnouncementPanel.vue'
import DashboardAsyncState from '../../components/dashboard/DashboardAsyncState.vue'
import { announcementsAPI } from '../../api/announcements.js'
import { dashboardAPI } from '../../api/dashboard.js'
import { useAuthStore } from '../../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()

const loading = ref(true)
const error = ref(false)
const dashboard = ref(null)

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

const continueRoute = computed(() => dashboard.value?.continue_learning?.route || null)

onMounted(loadDashboard)
</script>

<template>
  <AppLayout>
    <div class="dash">
      <!-- 问候行：角色问候 + 日期 + 一个上下文主操作 -->
      <header class="greeting">
        <div class="greeting-text">
          <h1 class="greeting-title">你好，{{ firstName }}</h1>
          <p class="greeting-date">{{ todayText }}</p>
        </div>
        <button
          v-if="continueRoute"
          type="button"
          class="continue-btn"
          @click="go(continueRoute)"
        >
          继续学习
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M3 8h10 M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </header>

      <!-- 摘要条：横向指标条，非装饰卡片网格 -->
      <section class="summary-strip" aria-label="学习概况">
        <div class="summary-item">
          <span class="summary-num">{{ dashboard?.summary?.course_count ?? '—' }}</span>
          <span class="summary-label">课程</span>
        </div>
        <div class="summary-item">
          <span class="summary-num">{{ dashboard?.summary?.pending_assignment_count ?? '—' }}</span>
          <span class="summary-label">待交作业</span>
        </div>
        <div class="summary-item">
          <span class="summary-num">{{ dashboard?.summary?.upcoming_exam_count ?? '—' }}</span>
          <span class="summary-label">即将考试</span>
        </div>
        <div class="summary-item">
          <span class="summary-num">{{ dashboard?.summary?.unread_announcement_count ?? '—' }}</span>
          <span class="summary-label">未读公告</span>
        </div>
      </section>

      <!-- 主双列：今日重点 + 通知公告 -->
      <div class="main-grid">
        <section class="card panel-card">
          <h2 class="panel-title">今日重点</h2>
          <DashboardAsyncState
            :loading="loading"
            :error="error"
            :empty="!dashboard?.priority_items?.length"
            empty-title="暂无待办"
            empty-body="当前没有待完成的作业或考试"
            @retry="loadDashboard"
          >
            <ul v-if="dashboard" class="priority-list">
              <li
                v-for="item in dashboard.priority_items"
                :key="item.kind + '-' + item.id"
                class="priority-item"
              >
                <span class="urgency-dot" :class="'urgency-' + item.urgency" aria-hidden="true"></span>
                <button type="button" class="item-main" @click="go(item.route)">
                  <span class="item-title">{{ item.title }}</span>
                  <span class="item-meta">
                    {{ kindLabel[item.kind] || item.kind }}
                    <template v-if="item.course_title">· {{ item.course_title }}</template>
                    <template v-if="item.time_at">· {{ formatTime(item.time_at) }}</template>
                  </span>
                </button>
                <span class="urgency-text" :class="'urgency-' + item.urgency">
                  {{ urgencyText[item.urgency] || '常规' }}
                </span>
              </li>
            </ul>
          </DashboardAsyncState>
        </section>

        <section class="card panel-card">
          <AnnouncementPanel
            :announcements="dashboard?.announcements || []"
            :loading="loading"
            :error="error"
            :can-publish="false"
            @retry="loadDashboard"
            @mark-read="markRead"
          />
        </section>
      </div>

      <!-- 课程动态 -->
      <section class="card panel-card">
        <h2 class="panel-title">课程动态</h2>
        <DashboardAsyncState
          :loading="loading"
          :error="error"
          :empty="!dashboard?.courses?.length"
          empty-title="暂无课程"
          empty-body="加入课程后将在这里展示学习动态"
          @retry="loadDashboard"
        >
          <ul v-if="dashboard" class="course-snap-list">
            <li v-for="course in dashboard.courses" :key="course.id" class="course-snap">
              <button type="button" class="course-snap-link" @click="go(course.route)">
                {{ course.title }}
              </button>
              <span class="course-snap-meta">
                {{ course.pending_assignment_count }} 份待交 · {{ course.upcoming_exam_count }} 场考试
              </span>
            </li>
          </ul>
        </DashboardAsyncState>
      </section>

      <!-- 最新反馈 -->
      <section class="card panel-card">
        <h2 class="panel-title">最新反馈</h2>
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
              v-for="item in dashboard.recent_feedback"
              :key="item.kind + '-' + item.id"
              class="feedback-item"
            >
              <button type="button" class="feedback-link" @click="go(item.route)">
                <span class="feedback-title">{{ item.title }}</span>
                <span class="feedback-score">得分 {{ item.score ?? '—' }}</span>
              </button>
              <p class="feedback-text">{{ item.feedback || '暂无文字反馈' }}</p>
              <span class="feedback-meta">
                {{ item.course_title }} · {{ formatTime(item.graded_at) }}
              </span>
            </li>
          </ul>
        </DashboardAsyncState>
      </section>
    </div>
  </AppLayout>
</template>

<style scoped>
.dash { display: flex; flex-direction: column; gap: 24px; }

/* ── 问候行 ─────────────────────────────────────────────────── */
.greeting {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 4px 0;
}
.greeting-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.02em;
}
.greeting-date {
  margin: 4px 0 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.continue-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--primary);
  color: var(--surface);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
}
.continue-btn:hover { background: var(--primary-dark); }

/* ── 摘要条 ─────────────────────────────────────────────────── */
.summary-strip {
  display: flex;
  gap: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  overflow: hidden;
}
.summary-item {
  flex: 1;
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 14px 20px;
  border-right: 1px solid var(--border);
}
.summary-item:last-child { border-right: none; }
.summary-num {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1;
}
.summary-label {
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

/* ── 面板 ───────────────────────────────────────────────────── */
.panel-card { padding: 20px; }
.panel-title {
  margin: 0 0 14px;
  font-size: var(--text-base);
  font-weight: 700;
  color: var(--ink);
}

.main-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 20px;
  align-items: start;
}

/* ── 今日重点 ───────────────────────────────────────────────── */
.priority-list { list-style: none; margin: 0; padding: 0; }
.priority-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}
.priority-item:first-child { padding-top: 0; }
.priority-item:last-child { border-bottom: none; padding-bottom: 0; }

.urgency-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-tertiary);
}
.urgency-dot.urgency-urgent { background: var(--danger); }
.urgency-dot.urgency-soon { background: var(--warning); }

.item-main {
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
.item-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
}
.item-main:hover .item-title { color: var(--primary); }
.item-meta {
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.urgency-text {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  color: var(--text-secondary);
  background: var(--surface-raised);
}
.urgency-text.urgency-urgent { color: var(--danger); background: var(--danger-light); }
.urgency-text.urgency-soon { color: var(--warning); background: var(--warning-light); }

/* ── 课程动态 ───────────────────────────────────────────────── */
.course-snap-list { list-style: none; margin: 0; padding: 0; }
.course-snap {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}
.course-snap:last-child { border-bottom: none; }
.course-snap-link {
  background: none;
  border: none;
  padding: 0;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
  cursor: pointer;
  text-align: left;
}
.course-snap-link:hover { color: var(--primary); }
.course-snap-meta { font-size: var(--text-xs); color: var(--text-secondary); flex-shrink: 0; }

/* ── 最新反馈 ───────────────────────────────────────────────── */
.feedback-list { list-style: none; margin: 0; padding: 0; }
.feedback-item {
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}
.feedback-item:first-child { padding-top: 0; }
.feedback-item:last-child { border-bottom: none; padding-bottom: 0; }

.feedback-link {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  text-align: left;
}
.feedback-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
}
.feedback-link:hover .feedback-title { color: var(--primary); }
.feedback-score { font-size: var(--text-xs); font-weight: 600; color: var(--success); flex-shrink: 0; }
.feedback-text {
  margin: 4px 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}
.feedback-meta { font-size: var(--text-xs); color: var(--text-tertiary); }

/* ── 响应式 ─────────────────────────────────────────────────── */
@media (max-width: 1024px) {
  .main-grid { grid-template-columns: 1fr; }
}

@media (max-width: 768px) {
  /* 摘要条 2x2 网格：flex-basis 固定 50% 且禁止收缩，保证换行成两列 */
  .summary-strip { flex-wrap: wrap; }
  .summary-item {
    flex: 0 0 50%;
    box-sizing: border-box;
    border-right: none;
    border-bottom: 1px solid var(--border);
    padding: 12px 16px;
  }
  .summary-item:nth-last-child(-n + 2) { border-bottom: none; }
  .greeting { align-items: flex-start; flex-direction: column; }
  .panel-card { padding: 16px; }
}
</style>
