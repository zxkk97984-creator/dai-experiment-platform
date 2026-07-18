<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'
import { useAppStore } from '../../stores/app.js'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

const menuItems = computed(() => {
  if (auth.isStudent) return [
    { path: '/student/courses',     label: '课程列表', key: 'courses' },
    { path: '/student/assignments', label: '我的作业', key: 'assignments' },
    { path: '/student/exams',       label: '考试中心', key: 'exams' },
    { path: '/student/experiments', label: '实验模块', key: 'experiments' },
    { path: '/student/jupyter',     label: 'Jupyter',   key: 'jupyter' },
  ]
  if (auth.isTeacher) return [
    { path: '/teacher/courses',     label: '课程管理', key: 'courses' },
    { path: '/teacher/assignments', label: '作业管理', key: 'assignments' },
    { path: '/teacher/exams',       label: '考试管理', key: 'exams' },
  ]
  if (auth.isAdmin) return [
    { path: '/admin/users',         label: '用户管理', key: 'users' },
    { path: '/admin/courses',       label: '课程管理', key: 'courses' },
    { path: '/admin/experiments',   label: '实验模块', key: 'experiments' },
  ]
  return []
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
    <div class="sidebar-brand" @click="navigate(menuItems[0]?.path || '/')">
      <span class="brand-mark">D</span>
      <span class="brand-text" v-if="!app.sidebarCollapsed">
        <span class="brand-name">DAI</span>
        <span class="brand-sub">实验平台</span>
      </span>
    </div>

    <nav class="sidebar-nav">
      <button
        v-for="item in menuItems" :key="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
        @click="navigate(item.path)"
      >
        <span class="nav-indicator" aria-hidden="true"></span>
        <span class="nav-label" v-if="!app.sidebarCollapsed">{{ item.label }}</span>
      </button>
    </nav>

    <div class="sidebar-footer">
      <button
        class="collapse-btn"
        @click="app.toggleSidebar()"
        :title="app.sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" :style="app.sidebarCollapsed ? '' : 'transform: rotate(180deg)'">
          <path d="M5 2L9 7L5 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed; left: 0; top: 0; bottom: 0; width: 232px;
  background: var(--bg-sidebar);
  display: flex; flex-direction: column; z-index: 100;
  transition: width var(--duration-slow) var(--ease-out);
  border-right: 1px solid rgba(255,255,255,0.04);
}
.sidebar.collapsed { width: 60px; }

/* ── Brand ─────────────────────────────────────────────────────────── */
.sidebar-brand {
  display: flex; align-items: center; gap: 10px;
  padding: 20px 16px 18px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  user-select: none;
}
.brand-mark {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 400;
  color: #fff;
  background: var(--accent);
  width: 34px; height: 34px;
  display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-md);
  flex-shrink: 0;
  line-height: 1;
}
.brand-text {
  display: flex; flex-direction: column; gap: 0;
  white-space: nowrap; overflow: hidden;
}
.brand-name {
  font-size: 15px; font-weight: 600; color: #fff;
  letter-spacing: 0.04em; line-height: 1.1;
}
.brand-sub {
  font-size: 11px; color: var(--text-sidebar);
  letter-spacing: 0.05em; line-height: 1.1;
}

/* ── Navigation ─────────────────────────────────────────────────────── */
.sidebar-nav {
  flex: 1; padding: 10px 8px;
  display: flex; flex-direction: column; gap: 1px;
}

.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 10px;
  background: none; border: none;
  color: var(--text-sidebar);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  font-weight: 400;
  border-radius: var(--radius-md);
  width: 100%; text-align: left;
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
  position: relative;
}
.nav-item:hover {
  background: rgba(255,255,255,0.05);
  color: #c8cdd5;
}

/* Active state — indicator light on an instrument panel */
.nav-item.active {
  background: rgba(26,92,138,0.18);
  color: #fff;
  font-weight: 500;
}
.nav-item.active .nav-indicator {
  background: var(--accent);
  box-shadow: 0 0 6px rgba(224,85,61,0.5);
}

.nav-indicator {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: transparent;
  flex-shrink: 0;
  transition: background var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
}
.nav-label { white-space: nowrap; }

/* ── Footer ─────────────────────────────────────────────────────────── */
.sidebar-footer {
  padding: 10px 8px;
  border-top: 1px solid rgba(255,255,255,0.06);
}
.collapse-btn {
  width: 100%; display: flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,0.03); border: none;
  color: var(--text-sidebar); padding: 6px;
  border-radius: var(--radius-sm); cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
}
.collapse-btn:hover {
  background: rgba(255,255,255,0.08);
  color: #fff;
}

/* ── Collapsed state ────────────────────────────────────────────────── */
.sidebar.collapsed .sidebar-brand { justify-content: center; padding: 16px 0; }
.sidebar.collapsed .nav-item { justify-content: center; padding: 10px; }
.sidebar.collapsed .nav-indicator { width: 5px; height: 5px; }
</style>
