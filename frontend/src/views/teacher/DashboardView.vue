<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { useAuthStore } from '../../stores/auth.js'
import { coursesAPI } from '../../api/courses.js'
import { assignmentsAPI } from '../../api/assignments.js'
import { examsAPI } from '../../api/exams.js'

const router = useRouter()
const auth = useAuthStore()

const courseCount = ref(null)
const assignmentCount = ref(null)
const examCount = ref(null)

async function loadCounts() {
  try {
    const cRes = await coursesAPI.list({ per_page: 1 })
    const courses = cRes.data.items || cRes.data
    courseCount.value = Array.isArray(courses) ? courses.length : (courses.total ?? courses.length ?? null)
  } catch { courseCount.value = null }
  try {
    const aRes = await assignmentsAPI.list({ per_page: 1 })
    const assignments = aRes.data.items || aRes.data
    assignmentCount.value = Array.isArray(assignments) ? assignments.length : (assignments.total ?? assignments.length ?? null)
  } catch { assignmentCount.value = null }
  try {
    const eRes = await examsAPI.list({ per_page: 1 })
    const exams = eRes.data.items || eRes.data
    examCount.value = Array.isArray(exams) ? exams.length : (exams.total ?? exams.length ?? null)
  } catch { examCount.value = null }
}

onMounted(loadCounts)

const teacherName = (auth.user?.real_name || auth.user?.username || '老师').slice(0, 8)

const stats = [
  { key: 'courses',     label: '我管理的课程', value: courseCount,     unit: '门', color: 'blue',   icon: '📚', trend: '点击查看课程详情' },
  { key: 'assignments', label: '已布置作业',   value: assignmentCount, unit: '份', color: 'orange', icon: '✍️', trend: '含编程题与实验' },
  { key: 'exams',        label: '已创建考试',   value: examCount,        unit: '场', color: 'purple', icon: '📝', trend: '客观题 + 主观题' },
]

const pending = [
  { date: '今日', time: '15:40', title: '《决策树》作业三 提交 12 份待批改', meta: 'ASG-03 · 12 份待批改', status: 'warning', icon: '📥' },
  { date: '今日', time: '10:22', title: '《神经网络》实验二 共 8 名学生已提交', meta: 'EXP-02 · 平均用时 38 分钟', status: 'info', icon: '🧪' },
  { date: '昨日', time: '21:05', title: '期中考试题目集 已发布', meta: 'EXAM-MID · 共 8 道题', status: 'success', icon: '✅' },
]

const sections = [
  { num: '01', label: '课程管理',   sub: 'Courses',      desc: '创建与维护课程、章节、课时安排',         path: '/teacher/courses',     icon: '📚', color: 'blue' },
  { num: '02', label: '作业中心',   sub: 'Assignments',  desc: '布置作业、编写判题题目与用例',           path: '/teacher/assignments', icon: '✍️', color: 'orange' },
  { num: '03', label: '考试管理',   sub: 'Examinations', desc: '创建考试、查看成绩单与统计',             path: '/teacher/exams',       icon: '📝', color: 'purple' },
  { num: '04', label: '实验管理',   sub: 'Experiments',  desc: '创建实验模块、配置 JupyterLab 环境',     path: '/teacher/experiments', icon: '🧪', color: 'green' },
]

function go(p) { router.push(p) }
function statusText(s) {
  return s === 'success' ? '已完成' : s === 'warning' ? '待处理' : s === 'info' ? '通知' : '记录'
}
</script>

<template>
  <AppLayout>
    <div class="dash">
      <!-- ── Hero / Page Head ──────────────────────────────────────────── -->
      <header class="page-head hero">
        <div class="hero-content">
          <div class="hero-eyebrow">
            <span class="eyebrow-dot"></span>
            <span>教师工作台 · 在线</span>
          </div>
          <h1 class="hero-title">
            欢迎回来，{{ teacherName }} 👨‍🏫
          </h1>
          <p class="hero-sub">
            你有 <strong>3 项</strong>待办事项，其中 <strong>1 份作业</strong>需要批改。
          </p>
          <div class="hero-actions">
            <button class="btn-primary" @click="go('/teacher/assignments')">
              去批改作业
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M3 8h10 M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <button class="btn-ghost" @click="go('/teacher/courses')">
              管理课程
            </button>
          </div>
        </div>
        <div class="hero-visual" aria-hidden="true">
          <div class="insight-card">
            <div class="insight-emoji">📊</div>
            <div class="insight-body">
              <div class="insight-num">38<span class="insight-unit">min</span></div>
              <div class="insight-label">学生平均实验用时</div>
            </div>
          </div>
        </div>
      </header>

      <!-- ── Stats ──────────────────────────────────────────────────────── -->
      <section class="stats">
        <article v-for="s in stats" :key="s.key" class="card stat-card" :class="'stat-' + s.color">
          <div class="stat-icon">{{ s.icon }}</div>
          <div class="stat-body">
            <div class="stat-value">
              <!-- 已加载：显示数值；加载中：骨架；错误：'—' -->
              <span v-if="s.value !== null" class="stat-num">{{ s.value }}</span>
              <span v-else-if="s.value === null" class="stat-num stat-num--skeleton"></span>
              <span class="stat-unit">{{ s.unit }}</span>
            </div>
            <div class="stat-label">{{ s.label }}</div>
            <div class="stat-trend">{{ s.trend }}</div>
          </div>
        </article>
      </section>

      <!-- ── Main grid ──────────────────────────────────────────────────── -->
      <div class="dash-grid">
        <!-- 待办时间线 -->
        <section class="card panel-card">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">待办与近期提交</h2>
              <p class="panel-sub">{{ pending.length }} 项需要关注</p>
            </div>
            <span class="badge badge-warning">Pending</span>
          </div>
          <ul v-if="pending.length" class="timeline">
            <li v-for="(a, i) in pending" :key="i" class="tl-item">
              <div class="tl-icon" :class="'tl-' + a.status">{{ a.icon }}</div>
              <div class="tl-body">
                <div class="tl-title">{{ a.title }}</div>
                <div class="tl-meta">
                  <span class="tl-meta-code">{{ a.meta }}</span>
                  <span class="tl-sep">·</span>
                  <span class="tl-time">{{ a.date }} {{ a.time }}</span>
                </div>
              </div>
              <span class="badge" :class="'badge-' + a.status">{{ statusText(a.status) }}</span>
            </li>
          </ul>
          <div v-else class="empty-state">
            <p>🎉 暂无待办事项</p>
          </div>
        </section>

        <!-- 管理入口 -->
        <aside class="card panel-card">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">管理入口</h2>
              <p class="panel-sub">快速进入各管理模块</p>
            </div>
          </div>
          <div class="section-list">
            <button
              v-for="s in sections" :key="s.num"
              class="section-row"
              :class="'sec-' + s.color"
              @click="go(s.path)"
            >
              <div class="sec-icon">{{ s.icon }}</div>
              <div class="sec-body">
                <div class="sec-label">
                  <span class="sec-zh">{{ s.label }}</span>
                  <span class="sec-num">{{ s.num }}</span>
                </div>
                <p class="sec-desc">{{ s.desc }}</p>
              </div>
              <svg class="sec-arrow" width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M5 3l5 5-5 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </div>
        </aside>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Teacher Dashboard — Code Studio
   Hero + KPI stats（异步加载 + 骨架屏）+ pending timeline + section dir.
   设计系统：全局 card / badge / btn-*，颜色全用 var()
   ═══════════════════════════════════════════════════════════════════════ */
.dash { display: flex; flex-direction: column; gap: 32px; }

/* ── Hero ─────────────────────────────────────────────────────────── */
.hero {
  background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 70%, var(--primary) 100%);
  border-radius: var(--radius-2xl);
  padding: 36px 36px;
  color: #FFFFFF;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 24px;
  align-items: center;
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-xl);
}
.hero::before {
  content: '';
  position: absolute; inset: 0;
  background-image:
    radial-gradient(circle at 85% 20%, rgba(249, 115, 22, 0.3) 0%, transparent 45%),
    radial-gradient(circle at 20% 80%, rgba(139, 92, 246, 0.18) 0%, transparent 50%);
  pointer-events: none;
}
.hero::after {
  content: '';
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 28px 28px;
  pointer-events: none;
}

.hero-content { position: relative; z-index: 1; }
.hero-eyebrow {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 5px 11px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  color: rgba(255, 255, 255, 0.85);
  font-weight: 500;
  margin-bottom: 14px;
}
.eyebrow-dot {
  width: 6px; height: 6px;
  background: var(--success);
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.3);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.3); }
  50%      { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
}
.hero-title {
  font-size: 30px;
  font-weight: 700;
  color: #FFFFFF;
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin: 0 0 10px;
}
.hero-sub {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.55;
  margin: 0 0 18px;
}
.hero-sub strong { color: var(--warning-soft); font-weight: 600; }
.hero-actions {
  display: flex; gap: 10px; flex-wrap: wrap;
}
.hero-actions .btn-primary {
  background: #FFFFFF;
  color: #1E3A8A;
  border-color: #FFFFFF;
  font-weight: 600;
}
.hero-actions .btn-primary:hover {
  background: rgba(255, 255, 255, 0.92);
  color: var(--primary-dark);
  box-shadow: 0 8px 20px rgba(255, 255, 255, 0.2);
}
.hero-actions .btn-ghost {
  background: rgba(255, 255, 255, 0.08);
  color: #FFFFFF;
  border: 1px solid rgba(255, 255, 255, 0.2);
}
.hero-actions .btn-ghost:hover {
  background: rgba(255, 255, 255, 0.15);
  color: #FFFFFF;
  border-color: rgba(255, 255, 255, 0.3);
}

.hero-visual { position: relative; z-index: 1; }
.insight-card {
  display: flex; align-items: center; gap: 14px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: var(--radius-xl);
  padding: 18px 22px;
  backdrop-filter: blur(10px);
}
.insight-emoji { font-size: 32px; line-height: 1; }
.insight-num {
  font-size: 28px;
  font-weight: 700;
  color: var(--warning-soft);
  letter-spacing: -0.02em;
  line-height: 1;
}
.insight-unit {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500; margin-left: 4px;
}
.insight-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500; letter-spacing: 0.04em; margin-top: 4px;
}

/* ── Stats — 复用 .card，异步加载带骨架屏 ──────────────────────── */
.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.stat-card {
  padding: 18px;
  display: flex; align-items: flex-start; gap: 14px;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
.stat-card:hover { transform: translateY(-2px); }
.stat-icon {
  width: 40px; height: 40px;
  border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; flex-shrink: 0;
  background: var(--primary-light);
}
.stat-blue .stat-icon   { background: var(--primary-light); }
.stat-orange .stat-icon { background: var(--accent-light); }
.stat-purple .stat-icon { background: var(--purple-light); }

.stat-body { flex: 1; min-width: 0; }
.stat-value {
  display: flex; align-items: baseline; gap: 3px;
  font-family: var(--font-display);
  font-weight: 700; margin-bottom: 2px;
}
.stat-num {
  font-size: 24px;
  color: var(--ink);
  letter-spacing: -0.02em; line-height: 1;
}
/* 骨架屏：异步数据未到达时显示 */
.stat-num--skeleton {
  display: inline-block;
  width: 48px; height: 24px;
  background: linear-gradient(90deg, var(--border) 25%, var(--surface-raised) 50%, var(--border) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.6s infinite;
  border-radius: var(--radius-sm);
  vertical-align: middle;
}
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.stat-unit {
  font-size: var(--text-xs);
  color: var(--text-secondary); font-weight: 500;
}
.stat-label {
  font-size: var(--text-sm);
  color: var(--ink); font-weight: 500; margin-bottom: 4px;
}
.stat-trend {
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
}

/* ── Dash grid ─────────────────────────────────────────────────────── */
.dash-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 24px;
  align-items: start;
}

/* 面板卡片 */
.panel-card { padding: 24px; }
.panel-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 18px;
}
.panel-title {
  font-size: 17px; font-weight: 600;
  color: var(--ink); letter-spacing: -0.01em; margin: 0;
}
.panel-sub {
  font-size: var(--text-xs); color: var(--text-secondary); margin: 3px 0 0;
}

/* 时间线 */
.timeline { list-style: none; padding: 0; margin: 0; }
.tl-item {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid var(--border);
}
.tl-item:first-child { padding-top: 0; }
.tl-item:last-child { border-bottom: none; padding-bottom: 0; }
.tl-icon {
  width: 36px; height: 36px;
  border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; flex-shrink: 0;
  background: var(--primary-light);
}
.tl-warning .tl-icon { background: var(--accent-light); }
.tl-info .tl-icon    { background: var(--primary-light); }
.tl-success .tl-icon { background: var(--success-light); }
.tl-neutral .tl-icon { background: var(--surface-sunken); }

.tl-body { flex: 1; min-width: 0; }
.tl-title {
  font-size: var(--text-sm); font-weight: 500;
  color: var(--ink); line-height: 1.4; margin-bottom: 4px;
}
.tl-meta {
  display: flex; gap: 6px;
  font-size: 11px; color: var(--text-secondary); flex-wrap: wrap;
}
.tl-meta-code { font-family: var(--font-mono); color: var(--text-tertiary); }
.tl-sep { color: var(--text-tertiary); }
.tl-time { color: var(--text-tertiary); }

/* 管理入口列表 */
.section-list {
  display: flex; flex-direction: column; gap: 10px;
}
.section-row {
  display: flex; align-items: center; gap: 14px;
  background: var(--surface-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  cursor: pointer; text-align: left; width: 100%;
  transition: border-color var(--duration-fast) var(--ease-out),
              background var(--duration-fast) var(--ease-out),
              transform var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
}
.section-row:hover {
  border-color: var(--border-strong);
  background: var(--surface);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}
.sec-icon {
  width: 38px; height: 38px;
  border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  font-size: 17px; flex-shrink: 0;
  background: var(--primary-light);
}
.sec-blue .sec-icon   { background: var(--primary-light); }
.sec-orange .sec-icon { background: var(--accent-light); }
.sec-purple .sec-icon { background: var(--purple-light); }
.sec-green .sec-icon  { background: var(--success-light); }

.sec-body { flex: 1; min-width: 0; }
.sec-label {
  display: flex; align-items: baseline; gap: 8px;
  margin-bottom: 2px;
}
.sec-zh {
  font-size: var(--text-sm); font-weight: 600;
  color: var(--ink); letter-spacing: -0.005em; line-height: 1.2;
}
.sec-num {
  font-size: 11px;
  font-family: var(--font-mono); color: var(--text-tertiary);
  font-weight: 500; letter-spacing: 0.04em;
}
.sec-desc {
  font-size: var(--text-xs); color: var(--text-secondary);
  line-height: 1.4; margin: 0;
}
.sec-arrow {
  color: var(--text-tertiary); flex-shrink: 0;
  transition: transform var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
}
.section-row:hover .sec-arrow { color: var(--primary); transform: translateX(2px); }

/* ── Responsive ─────────────────────────────────────────────────────── */
@media (max-width: 1024px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .dash-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .hero { grid-template-columns: 1fr; padding: 24px; }
  .hero-visual { display: none; }
  .hero-title { font-size: 24px; }
  .stats { grid-template-columns: 1fr; gap: 12px; }
  .stat-card { padding: 14px; }
  .stat-num { font-size: 20px; }
  .panel-card { padding: 18px; }
}
</style>
