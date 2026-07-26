<script setup>
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { useAuthStore } from '../../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()

const firstName = (auth.user?.real_name || auth.user?.username || '同学').slice(0, 6)

const stats = [
  { label: '进行中课程', value: 5,   unit: '门',  color: 'blue',   icon: '📚', trend: '+1 本周' },
  { label: '待交作业',   value: 3,   unit: '份',  color: 'orange', icon: '✍️', trend: '最近 1 份今日截止' },
  { label: '即将考试',   value: 2,   unit: '场',  color: 'purple', icon: '📝', trend: '11.20 期中考试' },
  { label: '近期均分',   value: 86,  unit: '分',  color: 'green',  icon: '🎯', trend: '+4 vs 上期' },
]

const courses = [
  { id: 1, title: '机器学习导论',    code: 'ML-101',  progress: 64, lessons: 16, current: 10, color: 'blue'   },
  { id: 2, title: 'Python 程序设计', code: 'PY-201',  progress: 82, lessons: 20, current: 16, color: 'green'  },
  { id: 3, title: '数据结构与算法',  code: 'DS-301',  progress: 38, lessons: 18, current: 7,  color: 'orange' },
  { id: 4, title: '深度学习实践',    code: 'DL-401',  progress: 12, lessons: 14, current: 2,  color: 'purple' },
]

const todos = [
  { id: 1, type: 'assignment', title: '实验三：数据预处理与特征工程', course: '机器学习导论',  due: '今日 23:59', priority: 'high',   done: false },
  { id: 2, type: 'assignment', title: '作业四：列表推导式与生成器',     course: 'Python 程序设计', due: '明日 23:59', priority: 'medium', done: false },
  { id: 3, type: 'exam',       title: '期中考试 · 客观题部分',         course: '机器学习导论',  due: '11.20 14:00', priority: 'high',   done: false },
  { id: 4, type: 'reading',    title: '阅读：决策树与随机森林',         course: '机器学习导论',  due: '本周内',       priority: 'low',    done: false },
]

const shortcuts = [
  { label: '课程',     sub: 'Courses',      icon: '📚', path: '/student/courses',     color: 'blue' },
  { label: '作业',     sub: 'Assignments',  icon: '✍️', path: '/student/assignments', color: 'orange' },
  { label: '考试',     sub: 'Exams',        icon: '📝', path: '/student/exams',       color: 'purple' },
  { label: '实验',     sub: 'Lab',          icon: '🧪', path: '/student/experiments', color: 'green' },
]

function go(path) { router.push(path) }
function goCourse(id) { router.push(`/student/courses/${id}`) }
</script>

<template>
  <AppLayout>
    <div class="dash">
      <!-- ── Hero / Page Head ──────────────────────────────────────────── -->
      <header class="page-head hero">
        <div class="hero-content">
          <div class="hero-eyebrow">
            <span class="eyebrow-dot"></span>
            <span>今日学习目标 · 2 / 3 已完成</span>
          </div>
          <h1 class="hero-title">
            继续加油，{{ firstName }} 👋
          </h1>
          <p class="hero-sub">
            你已经连续学习 <strong>7 天</strong>，距离本周目标还差 <strong>1 份作业</strong>。
          </p>
          <div class="hero-actions">
            <button class="btn-primary" @click="go('/student/assignments')">
              继续做作业
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M3 8h10 M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <button class="btn-ghost" @click="go('/student/experiments')">
              进入实验环境
            </button>
          </div>
        </div>
        <div class="hero-visual" aria-hidden="true">
          <div class="streak-card">
            <div class="streak-emoji">🔥</div>
            <div class="streak-body">
              <div class="streak-num">7</div>
              <div class="streak-label">天连续学习</div>
            </div>
          </div>
        </div>
      </header>

      <!-- ── Stats ──────────────────────────────────────────────────────── -->
      <section class="stats">
        <article v-for="s in stats" :key="s.label" class="card stat-card" :class="'stat-' + s.color">
          <div class="stat-icon">{{ s.icon }}</div>
          <div class="stat-body">
            <div class="stat-value">
              <span class="stat-num">{{ s.value }}</span>
              <span class="stat-unit">{{ s.unit }}</span>
            </div>
            <div class="stat-label">{{ s.label }}</div>
            <div class="stat-trend">{{ s.trend }}</div>
          </div>
        </article>
      </section>

      <!-- ── Main grid ──────────────────────────────────────────────────── -->
      <div class="dash-grid">
        <!-- 我的课程 -->
        <section class="card panel-card">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">我的课程</h2>
              <p class="panel-sub">继续上次学习</p>
            </div>
            <button class="btn-ghost btn-sm" @click="go('/student/courses')">
              全部 →
            </button>
          </div>
          <!-- 有课程时显示列表 -->
          <div v-if="courses.length" class="course-list">
            <div
              v-for="c in courses" :key="c.id"
              class="course-card"
              :class="'course-' + c.color"
              @click="goCourse(c.id)"
            >
              <div class="course-color" aria-hidden="true"></div>
              <div class="course-body">
                <div class="course-head">
                  <div>
                    <div class="course-code">{{ c.code }}</div>
                    <div class="course-title">{{ c.title }}</div>
                  </div>
                  <div class="course-progress-num">{{ c.progress }}%</div>
                </div>
                <div class="course-bar">
                  <div class="progress" :class="'progress-' + (c.progress >= 70 ? 'success' : c.progress >= 40 ? '' : 'warning')">
                    <div class="progress-bar" :style="{width: c.progress + '%'}"></div>
                  </div>
                </div>
                <div class="course-meta">
                  <span>📚 {{ c.current }} / {{ c.lessons }} 节</span>
                  <span>·</span>
                  <span>{{ c.progress >= 70 ? '即将完成' : c.progress >= 40 ? '稳步进行' : '刚开始' }}</span>
                </div>
              </div>
            </div>
          </div>
          <!-- 空状态 -->
          <div v-else class="empty-state">
            <p>📭 暂未加入任何课程</p>
            <button class="btn-primary btn-sm" @click="go('/student/courses')">浏览课程</button>
          </div>
        </section>

        <!-- 待办事项 -->
        <section class="card panel-card">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">待办事项</h2>
              <p class="panel-sub">{{ todos.filter(t => !t.done).length }} 项待处理</p>
            </div>
          </div>
          <ul v-if="todos.length" class="todo-list">
            <li v-for="t in todos" :key="t.id" class="todo-item">
              <div class="todo-checkbox" :class="{ checked: t.done }" aria-hidden="true">
                <svg v-if="t.done" width="10" height="10" viewBox="0 0 12 12" fill="none">
                  <path d="M2.5 6.5l2.5 2.5 4.5-5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
              <div class="todo-body">
                <div class="todo-title" :class="{ done: t.done }">{{ t.title }}</div>
                <div class="todo-meta">
                  <span class="todo-course">{{ t.course }}</span>
                  <span class="todo-sep">·</span>
                  <span class="todo-due" :class="'due-' + t.priority">⏰ {{ t.due }}</span>
                </div>
              </div>
              <span class="badge" :class="t.priority === 'high' ? 'badge-danger' : t.priority === 'medium' ? 'badge-warning' : 'badge-neutral'">
                {{ t.priority === 'high' ? '紧急' : t.priority === 'medium' ? '重要' : '常规' }}
              </span>
            </li>
          </ul>
          <div v-else class="empty-state">
            <p>🎉 暂无待办事项，继续保持！</p>
          </div>
        </section>
      </div>

      <!-- ── 快捷入口 ──────────────────────────────────────────────────── -->
      <section class="shortcuts">
        <div class="panel-head">
          <h2 class="panel-title">快速入口</h2>
        </div>
        <div class="shortcut-grid">
          <button
            v-for="s in shortcuts" :key="s.label"
            class="card shortcut-card"
            :class="'sc-' + s.color"
            @click="go(s.path)"
          >
            <div class="sc-icon">{{ s.icon }}</div>
            <div class="sc-body">
              <div class="sc-label">{{ s.label }}</div>
              <div class="sc-sub">{{ s.sub }}</div>
            </div>
            <svg class="sc-arrow" width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M5 3l5 5-5 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
      </section>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   Student Dashboard — Code Studio
   Hero + KPI stats + course progress + todos + shortcuts.
   设计系统：全局 card / badge / btn-* / progress，颜色全用 var()
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
.streak-card {
  display: flex; align-items: center; gap: 14px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: var(--radius-xl);
  padding: 18px 22px;
  backdrop-filter: blur(10px);
}
.streak-emoji { font-size: 32px; line-height: 1; }
.streak-num {
  font-size: 28px;
  font-weight: 700;
  color: var(--warning-soft);
  letter-spacing: -0.02em;
  line-height: 1;
}
.streak-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
  letter-spacing: 0.04em;
  margin-top: 4px;
}

/* ── Stats — 复用 .card 提供 bg/border/radius/hover ─────────────── */
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.stat-card {
  padding: 18px;
  display: flex; align-items: flex-start; gap: 14px;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
.stat-card:hover {
  transform: translateY(-2px);
}
.stat-icon {
  width: 40px; height: 40px;
  border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  background: var(--primary-light);
}
.stat-blue .stat-icon   { background: var(--primary-light); }
.stat-orange .stat-icon { background: var(--accent-light); }
.stat-purple .stat-icon { background: var(--purple-light); }
.stat-green .stat-icon  { background: var(--success-light); }

.stat-body { flex: 1; min-width: 0; }
.stat-value {
  display: flex; align-items: baseline; gap: 3px;
  font-family: var(--font-display);
  font-weight: 700;
  margin-bottom: 2px;
}
.stat-num {
  font-size: 24px;
  color: var(--ink);
  letter-spacing: -0.02em;
  line-height: 1;
}
.stat-unit {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  font-weight: 500;
}
.stat-label {
  font-size: var(--text-sm);
  color: var(--ink);
  font-weight: 500;
  margin-bottom: 4px;
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

/* 面板卡片 — 继承全局 .card，仅覆盖 padding */
.panel-card {
  padding: 24px;
}
.panel-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 18px;
}
.panel-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.01em;
  margin: 0;
}
.panel-sub {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin: 3px 0 0;
}

/* 课程卡片 */
.course-list {
  display: flex; flex-direction: column; gap: 12px;
}
.course-card {
  display: flex;
  background: var(--surface-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-out),
              background var(--duration-fast) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
.course-card:hover {
  border-color: var(--border-strong);
  background: var(--surface);
  transform: translateX(2px);
}
.course-color {
  width: 4px;
  flex-shrink: 0;
  background: var(--primary);
}
.course-blue .course-color   { background: var(--primary); }
.course-green .course-color  { background: var(--success); }
.course-orange .course-color { background: var(--accent); }
.course-purple .course-color { background: var(--purple); }

.course-body { flex: 1; padding: 14px 16px; min-width: 0; }
.course-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 10px; gap: 12px;
}
.course-code {
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-weight: 500;
  letter-spacing: 0.02em;
  margin-bottom: 2px;
}
.course-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.005em;
  line-height: 1.3;
}
.course-progress-num {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--primary);
  font-family: var(--font-mono);
  flex-shrink: 0;
}
.course-green .course-progress-num  { color: var(--success); }
.course-orange .course-progress-num { color: var(--accent); }
.course-purple .course-progress-num { color: var(--purple); }

.course-bar { margin-bottom: 8px; }
.course-meta {
  display: flex; gap: 6px;
  font-size: 11px;
  color: var(--text-secondary);
}

/* 待办列表 */
.todo-list { list-style: none; padding: 0; margin: 0; }
.todo-item {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}
.todo-item:first-child { padding-top: 0; }
.todo-item:last-child { border-bottom: none; padding-bottom: 0; }
.todo-checkbox {
  width: 20px; height: 20px;
  border: 1.5px solid var(--border-strong);
  border-radius: var(--radius-sm);
  flex-shrink: 0; margin-top: 1px;
  display: flex; align-items: center; justify-content: center;
  color: var(--surface);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              border-color var(--duration-fast) var(--ease-out);
}
.todo-checkbox:hover { border-color: var(--primary); }
.todo-checkbox.checked {
  background: var(--success);
  border-color: var(--success);
}
.todo-body { flex: 1; min-width: 0; }
.todo-title {
  font-size: var(--text-sm);
  color: var(--ink); font-weight: 500;
  line-height: 1.4; margin-bottom: 4px;
}
.todo-title.done { text-decoration: line-through; color: var(--text-tertiary); }
.todo-meta {
  display: flex; gap: 6px;
  font-size: 11px; color: var(--text-secondary);
}
.todo-course { color: var(--text-secondary); }
.todo-sep { color: var(--text-tertiary); }
.todo-due.due-high   { color: var(--danger); font-weight: 500; }
.todo-due.due-medium { color: var(--warning); }
.todo-due.due-low    { color: var(--text-tertiary); }

/* 快捷入口 — 复用 .card */
.shortcut-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.shortcut-card {
  display: flex; align-items: center; gap: 12px;
  padding: 16px;
  cursor: pointer; text-align: left; width: 100%;
  transition: border-color var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
.shortcut-card:hover { transform: translateY(-2px); }
.sc-icon {
  width: 36px; height: 36px;
  border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  font-size: 17px; flex-shrink: 0;
  background: var(--primary-light);
}
.sc-blue .sc-icon   { background: var(--primary-light); }
.sc-orange .sc-icon { background: var(--accent-light); }
.sc-purple .sc-icon { background: var(--purple-light); }
.sc-green .sc-icon  { background: var(--success-light); }

.sc-body { flex: 1; min-width: 0; }
.sc-label {
  font-size: var(--text-sm); font-weight: 600;
  color: var(--ink); letter-spacing: -0.005em; line-height: 1.2;
}
.sc-sub {
  font-size: 11px; color: var(--text-tertiary);
  font-family: var(--font-mono); margin-top: 2px;
}
.sc-arrow {
  color: var(--text-tertiary); flex-shrink: 0;
  transition: transform var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
}
.shortcut-card:hover .sc-arrow { color: var(--primary); transform: translateX(2px); }

/* ── Responsive ─────────────────────────────────────────────────────── */
@media (max-width: 1024px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .dash-grid { grid-template-columns: 1fr; }
  .shortcut-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
  .hero { grid-template-columns: 1fr; padding: 24px; }
  .hero-visual { display: none; }
  .hero-title { font-size: 24px; }
  .stats { grid-template-columns: 1fr 1fr; gap: 12px; }
  .stat-card { padding: 14px; }
  .stat-num { font-size: 20px; }
  .panel-card { padding: 18px; }
  .shortcut-grid { grid-template-columns: 1fr 1fr; }
}
</style>
