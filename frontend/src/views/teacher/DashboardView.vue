<script setup>
// 教师工作台：一次聚合请求渲染真实数据；工作队列优先，含课程公告发布

import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppLayout from '../../components/layout/AppLayout.vue'
import AnnouncementComposer from '../../components/dashboard/AnnouncementComposer.vue'
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
const showComposer = ref(false)
const panelRef = ref(null)

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

const urgencyText = { urgent: '紧急', soon: '即将', normal: '常规' }

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
  // 仅允许服务端返回的教师相对路由
  if (route === '/teacher' || route.startsWith('/teacher/')) {
    router.push(route)
  }
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
  return primaryWork()?.route || '/teacher/courses'
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
  // 发布成功后同样把焦点还给发布按钮
  nextTick(() => {
    panelRef.value?.$el?.querySelector('.publish-btn')?.focus()
  })
}

function onCloseComposer() {
  showComposer.value = false
  // 关闭后把焦点还给发布按钮
  nextTick(() => {
    panelRef.value?.$el?.querySelector('.publish-btn')?.focus()
  })
}

const primaryActionLabel = computed(() =>
  primaryWork() ? '处理工作' : '管理课程',
)

onMounted(loadDashboard)
</script>

<template>
  <AppLayout>
    <div class="dash">
      <!-- 问候行：角色问候 + 日期 + 一个上下文主操作 -->
      <header class="greeting">
        <div class="greeting-text">
          <h1 class="greeting-title">你好，{{ teacherName }}</h1>
          <p class="greeting-date">{{ todayText }}</p>
        </div>
        <button
          type="button"
          class="work-queue-btn"
          @click="go(primaryActionRoute())"
        >
          {{ primaryActionLabel }}
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M3 8h10 M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </header>

      <!-- 摘要条 -->
      <section class="summary-strip" aria-label="工作概况">
        <div class="summary-item">
          <span class="summary-num">{{ dashboard?.summary?.course_count ?? '—' }}</span>
          <span class="summary-label">课程</span>
        </div>
        <div class="summary-item">
          <span class="summary-num">{{ dashboard?.summary?.student_count ?? '—' }}</span>
          <span class="summary-label">学生</span>
        </div>
        <div class="summary-item">
          <span class="summary-num">{{ dashboard?.summary?.pending_review_count ?? '—' }}</span>
          <span class="summary-label">待复核</span>
        </div>
        <div class="summary-item">
          <span class="summary-num">{{ dashboard?.summary?.upcoming_deadline_count ?? '—' }}</span>
          <span class="summary-label">近 7 天截止</span>
        </div>
      </section>

      <!-- 主双列：待处理工作 + 通知公告 -->
      <div class="main-grid">
        <section class="card panel-card">
          <h2 class="panel-title">待处理工作</h2>
          <DashboardAsyncState
            :loading="loading"
            :error="error"
            :empty="!dashboard?.work_items?.length"
            empty-title="暂无待处理工作"
            empty-body="当前没有需要复核或即将截止的任务"
            @retry="loadDashboard"
          >
            <ul v-if="dashboard" class="work-list">
              <li
                v-for="item in dashboard.work_items"
                :key="item.kind + '-' + item.id"
                class="work-item"
              >
                <span class="urgency-dot" :class="'urgency-' + item.urgency" aria-hidden="true"></span>
                <button type="button" class="work-item-link" @click="go(item.route)">
                  <span class="work-item-title">{{ item.title }}</span>
                  <span class="work-item-meta">
                    {{ item.course_title }}
                    <template v-if="item.time_at">· {{ formatTime(item.time_at) }}</template>
                  </span>
                </button>
                <span class="work-item-detail">{{ item.detail }}</span>
              </li>
            </ul>
          </DashboardAsyncState>
        </section>

        <section class="card panel-card">
          <AnnouncementPanel
            ref="panelRef"
            :announcements="dashboard?.announcements || []"
            :loading="loading"
            :error="error"
            :can-publish="true"
            @retry="loadDashboard"
            @publish="showComposer = true"
            @mark-read="markRead"
          />
        </section>
      </div>

      <!-- 课程概览 -->
      <section class="card panel-card">
        <h2 class="panel-title">课程概览</h2>
        <DashboardAsyncState
          :loading="loading"
          :error="error"
          :empty="!dashboard?.course_health?.length"
          empty-title="暂无课程"
          empty-body="创建课程后，健康度会展示在这里"
          @retry="loadDashboard"
        >
          <ul v-if="dashboard" class="health-list">
            <li v-for="row in dashboard.course_health" :key="row.course_id" class="health-row">
              <button type="button" class="health-link" @click="go(row.route)">
                {{ row.title }}
              </button>
              <span class="health-meta">
                {{ row.student_count }} 名学生
                <template v-if="row.pending_review_count">· {{ row.pending_review_count }} 项待复核</template>
                <template v-if="row.upcoming_deadline_count">· {{ row.upcoming_deadline_count }} 项即将截止</template>
                ·
                <template v-if="row.at_risk_expected_count">
                  {{ row.at_risk_submitted_count ?? 0 }}/{{ row.at_risk_expected_count }} 已提交
                </template>
                <template v-else>—</template>
              </span>
            </li>
          </ul>
        </DashboardAsyncState>
      </section>

      <!-- 最近动态 -->
      <section class="card panel-card">
        <h2 class="panel-title">最近动态</h2>
        <DashboardAsyncState
          :loading="loading"
          :error="error"
          :empty="!dashboard?.recent_activity?.length"
          empty-title="暂无动态"
          empty-body="学生提交后，动态会出现在这里"
          @retry="loadDashboard"
        >
          <ul v-if="dashboard" class="activity-list">
            <li
              v-for="item in dashboard.recent_activity"
              :key="item.kind + '-' + item.id"
              class="activity-item"
            >
              <button type="button" class="activity-link" @click="go(item.route)">
                {{ item.title }}
              </button>
              <span class="activity-meta">
                {{ item.course_title }} · {{ formatTime(item.happened_at) }}
              </span>
            </li>
          </ul>
        </DashboardAsyncState>
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
.work-queue-btn {
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
.work-queue-btn:hover { background: var(--primary-dark); }

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

/* ── 待处理工作 ─────────────────────────────────────────────── */
.work-list { list-style: none; margin: 0; padding: 0; }
.work-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}
.work-item:first-child { padding-top: 0; }
.work-item:last-child { border-bottom: none; padding-bottom: 0; }

.urgency-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-tertiary);
}
.urgency-dot.urgency-urgent { background: var(--danger); }
.urgency-dot.urgency-soon { background: var(--warning); }

.work-item-link {
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
.work-item-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
}
.work-item-link:hover .work-item-title { color: var(--primary); }
.work-item-meta {
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.work-item-detail {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  color: var(--warning);
  background: var(--warning-light);
}

/* ── 课程概览 ───────────────────────────────────────────────── */
.health-list { list-style: none; margin: 0; padding: 0; }
.health-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}
.health-row:last-child { border-bottom: none; }
.health-link {
  background: none;
  border: none;
  padding: 0;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
  cursor: pointer;
  text-align: left;
}
.health-link:hover { color: var(--primary); }
.health-meta { font-size: var(--text-xs); color: var(--text-secondary); flex-shrink: 0; }

/* ── 最近动态 ───────────────────────────────────────────────── */
.activity-list { list-style: none; margin: 0; padding: 0; }
.activity-item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}
.activity-item:last-child { border-bottom: none; }
.activity-link {
  background: none;
  border: none;
  padding: 0;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--ink);
  cursor: pointer;
  text-align: left;
}
.activity-link:hover { color: var(--primary); }
.activity-meta { font-size: var(--text-xs); color: var(--text-tertiary); flex-shrink: 0; }

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
