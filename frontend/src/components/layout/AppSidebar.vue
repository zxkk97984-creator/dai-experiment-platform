<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'
import { useAppStore } from '../../stores/app.js'
import { homeForRole } from '../../router/roleHome.js'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

// Modern icons — clean line style
const ICONS = {
  home:        'M3 10l9-7 9 7 M5 9v11h14V9',
  courses:     'M4 4h6l2 2h8v10H4V4z M4 18h16',
  assignments: 'M9 5l-5 5 5 5 M15 5l5 5-5 5',
  exams:       'M5 3h12v18H5V3z M8 8h6 M8 12h4',
  experiments: 'M10 3v6h4V3 M8 9h8v12H8V9z',
  users:       'M8 7a3 3 0 100-6 3 3 0 000 6z M2 19c0-3.3 2.7-6 6-6s6 2.7 6 6',
}

const menuItems = computed(() => {
  const home = (root) => ({ path: root, label: '首页', sub: 'Home', icon: 'home', key: 'home' })
  const base = [
    { path: '/student/courses',     label: '课程',     sub: 'Courses',     icon: 'courses',     key: 'courses' },
    { path: '/student/assignments', label: '作业',     sub: 'Assignments', icon: 'assignments', key: 'assignments' },
    { path: '/student/exams',       label: '考试',     sub: 'Exams',       icon: 'exams',       key: 'exams' },
    { path: '/student/experiments', label: '实验',     sub: 'Lab',         icon: 'experiments', key: 'experiments' },
  ]
  if (auth.isTeacher) return [
    home('/teacher'),
    { path: '/teacher/courses',     label: '课程',     sub: 'Courses',      icon: 'courses',     key: 'courses' },
    { path: '/teacher/assignments', label: '作业',     sub: 'Assignments',  icon: 'assignments', key: 'assignments' },
    { path: '/teacher/exams',       label: '考试',     sub: 'Exams',        icon: 'exams',       key: 'exams' },
    { path: '/teacher/experiments', label: '实验',     sub: 'Experiments',  icon: 'experiments', key: 'experiments' },
    { path: '/teacher/submissions', label: '提交列表', sub: 'Submissions',  icon: 'assignments', key: 'submissions' },
    { path: '/teacher/ai-grading',  label: 'AI 评分',   sub: 'AI Grading',    icon: 'assignments', key: 'ai-grading' },
  ]
  if (auth.isAdmin) return [
    { path: '/admin/users',         label: '用户',     sub: 'Users',       icon: 'users',       key: 'users' },
    { path: '/admin/courses',       label: '课程',     sub: 'Courses',     icon: 'courses',     key: 'courses' },
    { path: '/admin/experiments',   label: '实验',     sub: 'Experiments', icon: 'experiments', key: 'experiments' },
    { path: '/admin/ai-grading',    label: 'AI 评分',   sub: 'AI Grading',    icon: 'assignments', key: 'ai-grading' },
  ]
  if (auth.isDeveloper) return [
    {
      path: '/developer/templates',
      label: '实验模板',
      sub: 'Templates',
      icon: 'experiments',
      key: 'templates',
    },
  ]
  return [home('/student'), ...base]
})

function isActive(path) {
  if (path === '/student/assignments' && route.path.startsWith('/student/submissions')) return true
  if (path === '/teacher/submissions' && route.path.startsWith('/teacher/submissions')) return true
  if (path === '/admin/submissions' && route.path.startsWith('/admin/submissions')) return true
  // 角色首页项仅精确匹配根路由，子页面不高亮
  if (path === '/student' || path === '/teacher') return route.path === path
  return route.path.startsWith(path)
}

function navigate(path) {
  router.push(path)
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed: app.sidebarCollapsed }">
    <!-- Logo：真实 button，原生键盘可聚焦与回车激活 -->
    <button
      type="button"
      class="logo"
      aria-label="返回首页"
      @click="navigate(homeForRole(auth.role))"
    >
      <div class="logo-mark">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <path d="M12 2L3 7v10l9 5 9-5V7l-9-5z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
          <path d="M12 2v20 M3 7l9 5 9-5" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
        </svg>
      </div>
      <div class="logo-text" v-if="!app.sidebarCollapsed">
        <span class="logo-name">DAI 实验平台</span>
      </div>
    </button>

    <!-- Nav -->
    <nav class="nav">
      <div class="nav-label" v-if="!app.sidebarCollapsed">主导航</div>
      <button
        v-for="item in menuItems" :key="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
        :aria-label="item.label"
        @click="navigate(item.path)"
        :title="app.sidebarCollapsed ? item.label : ''"
      >
        <span class="nav-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
            <path :d="ICONS[item.icon]" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </span>
        <span class="nav-text" v-if="!app.sidebarCollapsed">{{ item.label }}</span>
        <span class="nav-active-dot" v-if="isActive(item.path)"></span>
      </button>
    </nav>

    <!-- Footer -->
    <div class="sidebar-footer">
      <button
        class="collapse-btn"
        @click="app.toggleSidebar()"
        :title="app.sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
        aria-label="Toggle sidebar"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none"
             :style="app.sidebarCollapsed ? 'transform: rotate(180deg)' : ''">
          <path d="M10 3l-5 5 5 5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span v-if="!app.sidebarCollapsed" class="collapse-text">收起</span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   App Sidebar — Light theme
   白底 + 右侧边框 + 蓝色 active 态
   ═══════════════════════════════════════════════════════════════════════ */
.sidebar {
  position: fixed;
  left: 0; top: 0; bottom: 0;
  width: 224px;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  z-index: 100;
  transition: width var(--duration-slow) var(--ease-out);
  color: var(--ink);
  border-right: 1px solid var(--border);
}

.sidebar.collapsed { width: 56px; }

/* ── Logo ──────────────────────────────────────────────────────────── */
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid var(--border);
  /* button 原生样式重置：保持与既有 div 外观一致 */
  width: 100%;
  box-sizing: border-box;
  border-left: none;
  border-top: none;
  border-right: none;
  background: none;
  font-family: inherit;
  text-align: left;
}

.logo-mark {
  width: 28px; height: 28px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  display: flex; align-items: center; justify-content: center;
  color: var(--surface);
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
}

.logo-text {
  display: flex; flex-direction: column; gap: 0px;
  min-width: 0;
}
.logo-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.01em;
  line-height: 1;
  white-space: nowrap;
}

.sidebar.collapsed .logo {
  padding: 16px 0;
  justify-content: center;
}

/* ── Nav ───────────────────────────────────────────────────────────── */
.nav {
  flex: 1;
  padding: 16px 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  padding: 12px 12px 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  font-weight: 500;
  width: 100%;
  text-align: left;
  cursor: pointer;
  position: relative;
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
  text-transform: none;
  letter-spacing: 0;
}

.nav-item:hover {
  background: var(--primary-light);
  color: var(--primary);
  border-color: transparent;
}

.nav-item.active {
  background: var(--primary-light);
  color: var(--primary);
}
.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0; top: 50%;
  transform: translateY(-50%);
  width: 2px; height: 16px;
  background: var(--primary);
  border-radius: 0 var(--radius-xs) var(--radius-xs) 0;
}

.nav-icon {
  display: flex; align-items: center; justify-content: center;
  width: 20px; height: 20px;
  flex-shrink: 0;
  color: currentColor;
}

.nav-text {
  font-size: var(--text-sm);
  font-weight: 500;
  line-height: 1.3;
  color: inherit;
}

.nav-active-dot {
  display: none;
  position: absolute;
  right: 8px; top: 50%;
  transform: translateY(-50%);
  width: 6px; height: 6px;
  background: var(--primary);
  border-radius: 50%;
}
.sidebar.collapsed .nav-active-dot { display: block; }

.sidebar.collapsed .nav { padding: 16px 8px; }
.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 12px 8px;
  gap: 0;
}
.sidebar.collapsed .nav-label { display: none; }

/* ── Footer ─────────────────────────────────────────────────────────── */
.sidebar-footer {
  padding: 12px;
  border-top: 1px solid var(--border);
}

.collapse-btn {
  width: 100%;
  display: flex; align-items: center; justify-content: center;
  gap: 8px;
  background: transparent;
  border: none;
  color: var(--text-tertiary);
  padding: 8px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
  text-transform: none;
  font-weight: 500;
}
.collapse-btn:hover {
  background: var(--surface-raised);
  color: var(--ink);
  border-color: transparent;
}
.collapse-text {
  font-size: var(--text-xs);
  letter-spacing: 0.02em;
}

.sidebar.collapsed .collapse-btn { padding: 8px 0; }

/* ── 移动端：强制紧凑图标栏（约 56px），避免固定 224px 侧栏挤压主内容 ── */
@media (max-width: 768px) {
  .sidebar { width: 56px; }
  .logo { justify-content: center; padding: 16px 0; }
  .logo-text,
  .nav-label,
  .nav-text,
  .collapse-text { display: none; }
  .nav { padding: 16px 8px; }
  .nav-item { justify-content: center; padding: 12px 8px; gap: 0; }
  .nav-active-dot { display: block; }
  /* 移动端侧栏固定为图标形态，折叠控件无实际效果，隐藏避免误导 */
  .collapse-btn { display: none; }
}
</style>
