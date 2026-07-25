<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

// Modern icons — clean line style
const ICONS = {
  courses:     'M4 4h6l2 2h8v10H4V4z M4 18h16',
  assignments: 'M9 5l-5 5 5 5 M15 5l5 5-5 5',
  exams:       'M5 3h12v18H5V3z M8 8h6 M8 12h4',
  experiments: 'M10 3v6h4V3 M8 9h8v12H8V9z',
  users:       'M8 7a3 3 0 100-6 3 3 0 000 6z M2 19c0-3.3 2.7-6 6-6s6 2.7 6 6',
}

const menuItems = computed(() => {
  const base = [
    { path: '/student/courses',     label: '课程',     sub: 'Courses',     icon: 'courses',     key: 'courses' },
    { path: '/student/assignments', label: '作业',     sub: 'Assignments', icon: 'assignments', key: 'assignments' },
    { path: '/student/exams',       label: '考试',     sub: 'Exams',       icon: 'exams',       key: 'exams' },
    { path: '/student/experiments', label: '实验',     sub: 'Lab',         icon: 'experiments', key: 'experiments' },
  ]
  if (auth.isTeacher) return [
    { path: '/teacher/courses',     label: '课程',     sub: 'Courses',      icon: 'courses',     key: 'courses' },
    { path: '/teacher/assignments', label: '作业',     sub: 'Assignments',  icon: 'assignments', key: 'assignments' },
    { path: '/teacher/exams',       label: '考试',     sub: 'Exams',        icon: 'exams',       key: 'exams' },
    { path: '/teacher/experiments', label: '实验',     sub: 'Experiments',  icon: 'experiments', key: 'experiments' },
  ]
  if (auth.isAdmin) return [
    { path: '/admin/users',         label: '用户',     sub: 'Users',       icon: 'users',       key: 'users' },
    { path: '/admin/courses',       label: '课程',     sub: 'Courses',     icon: 'courses',     key: 'courses' },
    { path: '/admin/experiments',   label: '实验',     sub: 'Experiments', icon: 'experiments', key: 'experiments' },
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
  return base
})

function isActive(path) {
  if (path === '/student/assignments' && route.path.startsWith('/student/submissions')) return true
  return route.path.startsWith(path)
}

function navigate(path) {
  router.push(path)
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed: app.sidebarCollapsed }">
    <!-- Logo -->
    <div class="logo" @click="navigate(menuItems[0]?.path || '/')">
      <div class="logo-mark">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <path d="M12 2L3 7v10l9 5 9-5V7l-9-5z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
          <path d="M12 2v20 M3 7l9 5 9-5" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
        </svg>
      </div>
      <div class="logo-text" v-if="!app.sidebarCollapsed">
        <span class="logo-name">DAI</span>
        <span class="logo-sub">实验平台</span>
      </div>
    </div>

    <!-- Nav -->
    <nav class="nav">
      <div class="nav-label" v-if="!app.sidebarCollapsed">主导航</div>
      <button
        v-for="item in menuItems" :key="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
        @click="navigate(item.path)"
        :title="app.sidebarCollapsed ? item.label : ''"
      >
        <span class="nav-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
            <path :d="ICONS[item.icon]" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </span>
        <span class="nav-body" v-if="!app.sidebarCollapsed">
          <span class="nav-label-text">{{ item.label }}</span>
          <span class="nav-sub">{{ item.sub }}</span>
        </span>
        <span class="nav-active-dot" v-if="isActive(item.path) && app.sidebarCollapsed"></span>
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
.sidebar {
  position: fixed;
  left: 0; top: 0; bottom: 0;
  width: 240px;
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  z-index: 100;
  transition: width var(--duration-slow) var(--ease-out);
  color: #FFFFFF;
}

.sidebar.collapsed { width: 64px; }

/* ── Logo ──────────────────────────────────────────────────────────── */
.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 18px;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.logo-mark {
  width: 36px; height: 36px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
  display: flex; align-items: center; justify-content: center;
  color: #FFFFFF;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
}

.logo-text {
  display: flex; flex-direction: column; gap: 1px;
  min-width: 0;
}
.logo-name {
  font-size: 16px;
  font-weight: 700;
  color: #FFFFFF;
  letter-spacing: -0.01em;
  line-height: 1;
}
.logo-sub {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 500;
  letter-spacing: 0.02em;
}

.sidebar.collapsed .logo {
  padding: 20px 0;
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
  color: rgba(255, 255, 255, 0.4);
  padding: 12px 12px 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: rgba(255, 255, 255, 0.7);
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
  background: rgba(255, 255, 255, 0.06);
  color: #FFFFFF;
  border-color: transparent;
}

.nav-item.active {
  background: rgba(37, 99, 235, 0.15);
  color: #FFFFFF;
}
.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0; top: 50%;
  transform: translateY(-50%);
  width: 3px; height: 18px;
  background: var(--primary);
  border-radius: 0 var(--radius-xs) var(--radius-xs) 0;
}

.nav-icon {
  display: flex; align-items: center; justify-content: center;
  width: 20px; height: 20px;
  flex-shrink: 0;
  color: currentColor;
}
.nav-item.active .nav-icon { color: var(--primary); }

.nav-body {
  display: flex; flex-direction: column; gap: 0px;
  flex: 1; min-width: 0;
}
.nav-label-text {
  font-size: 14px;
  font-weight: 500;
  line-height: 1.3;
  color: inherit;
}
.nav-sub {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  font-weight: 400;
  line-height: 1.3;
}
.nav-item.active .nav-sub { color: rgba(255, 255, 255, 0.55); }

.nav-active-dot {
  position: absolute;
  right: 8px; top: 50%;
  transform: translateY(-50%);
  width: 6px; height: 6px;
  background: var(--primary);
  border-radius: 50%;
}

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
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.collapse-btn {
  width: 100%;
  display: flex; align-items: center; justify-content: center;
  gap: 8px;
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.5);
  padding: 8px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
  text-transform: none;
  font-weight: 500;
}
.collapse-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #FFFFFF;
  border-color: transparent;
}
.collapse-text {
  font-size: 12px;
  letter-spacing: 0.02em;
}

.sidebar.collapsed .collapse-btn { padding: 8px 0; }
</style>
