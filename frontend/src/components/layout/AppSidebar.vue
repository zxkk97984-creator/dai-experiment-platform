<script setup>
// AppSidebar：共享认证侧栏。角色菜单与权限保持原样；
// 视觉按参考设计：白底、软填充激活行、无左侧条纹、真实图标库。

import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'
import { useAppStore } from '../../stores/app.js'
import { homeForRole } from '../../router/roleHome.js'
import AppIcon from '../ui/AppIcon.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

const menuItems = computed(() => {
  const home = (root) => ({ path: root, label: '首页', sub: 'Home', icon: 'home', key: 'home' })
  const base = [
    { path: '/student/courses',     label: '课程',     sub: 'Courses',     icon: 'course',     key: 'courses' },
    { path: '/student/assignments', label: '作业',     sub: 'Assignments', icon: 'assignment', key: 'assignments' },
    { path: '/student/exams',       label: '考试',     sub: 'Exams',       icon: 'exam',       key: 'exams' },
    { path: '/student/experiments', label: '实验',     sub: 'Lab',         icon: 'experiment', key: 'experiments' },
  ]
  if (auth.isTeacher) return [
    home('/teacher'),
    { path: '/teacher/courses',     label: '课程',     sub: 'Courses',      icon: 'course',     key: 'courses' },
    { path: '/teacher/assignments', label: '作业',     sub: 'Assignments',  icon: 'assignment', key: 'assignments' },
    { path: '/teacher/exams',       label: '考试',     sub: 'Exams',        icon: 'exam',       key: 'exams' },
    { path: '/teacher/experiments', label: '实验',     sub: 'Experiments',  icon: 'experiment', key: 'experiments' },
    { path: '/teacher/submissions', label: '提交列表', sub: 'Submissions',  icon: 'assignment', key: 'submissions' },
    { path: '/teacher/ai-grading',  label: 'AI 评分',   sub: 'AI Grading',    icon: 'assignment', key: 'ai-grading' },
  ]
  if (auth.isAdmin) return [
    { path: '/admin/users',         label: '用户',     sub: 'Users',       icon: 'user',       key: 'users' },
    { path: '/admin/courses',       label: '课程',     sub: 'Courses',     icon: 'course',     key: 'courses' },
    { path: '/admin/experiments',   label: '实验',     sub: 'Experiments', icon: 'experiment', key: 'experiments' },
    { path: '/admin/ai-grading',    label: 'AI 评分',   sub: 'AI Grading',    icon: 'assignment', key: 'ai-grading' },
  ]
  if (auth.isDeveloper) return [
    {
      path: '/developer/templates',
      label: '实验模板',
      sub: 'Templates',
      icon: 'experiment',
      key: 'templates',
    },
  ]
  return [home('/student'), ...base]
})

function isActive(path) {
  if (path === '/student/assignments' && route.path.startsWith('/student/submissions')) return true
  if (path === '/teacher/submissions' && route.path.startsWith('/teacher/submissions')) return true
  if (path === '/admin/submissions' && route.path.startsWith('/admin/submissions')) return true
  // 角色首页项：根路由精确匹配；/student/feedback 镜像参考图 01 归属首页
  if (path === '/student') return route.path === path || route.path === '/student/feedback'
  if (path === '/teacher') return route.path === path
  return route.path.startsWith(path)
}

function navigate(path) {
  router.push(path)
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed: app.sidebarCollapsed }">
    <!-- Logo：真实 button + 库图标（蓝色方块内的立方体） -->
    <button
      type="button"
      class="logo"
      aria-label="返回首页"
      @click="navigate(homeForRole(auth.role))"
    >
      <span class="logo-mark" aria-hidden="true">
        <AppIcon name="cube" :size="20" />
      </span>
      <span class="logo-text" v-if="!app.sidebarCollapsed">
        <span class="logo-name">DAI 实验平台</span>
      </span>
    </button>

    <!-- Nav -->
    <nav class="nav">
      <button
        v-for="item in menuItems" :key="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
        :aria-label="item.label"
        @click="navigate(item.path)"
        :title="app.sidebarCollapsed ? item.label : ''"
      >
        <span class="nav-icon" aria-hidden="true">
          <AppIcon :name="item.icon" :size="20" />
        </span>
        <span class="nav-text" v-if="!app.sidebarCollapsed">{{ item.label }}</span>
      </button>
    </nav>

    <!-- Footer：折叠动作，箭头旋转不依赖自定义 SVG -->
    <div class="sidebar-footer">
      <button
        class="collapse-btn"
        @click="app.toggleSidebar()"
        :title="app.sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
        aria-label="Toggle sidebar"
      >
        <span class="collapse-arrow" :class="{ 'is-collapsed': app.sidebarCollapsed }" aria-hidden="true">
          <AppIcon name="chevron-right" :size="16" />
        </span>
        <span v-if="!app.sidebarCollapsed" class="collapse-text">收起</span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════════
   App Sidebar — 参考设计：白底、右侧细边框、软填充激活行（无左侧条纹）
   ═══════════════════════════════════════════════════════════════════════ */
.sidebar {
  position: fixed;
  left: 0; top: 0; bottom: 0;
  width: var(--sidebar-width, 264px);
  background: var(--surface);
  display: flex;
  flex-direction: column;
  z-index: 100;
  transition: width var(--duration-slow) var(--ease-out);
  color: var(--ink);
  border-right: 1px solid var(--border);
}

.sidebar.collapsed { width: var(--sidebar-collapsed-width, 64px); }

/* ── Logo 行（82px 高） ─────────────────────────────────────────── */
.logo {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  padding: 16px;
  height: 82px;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid var(--border);
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
  width: 32px; height: 32px;
  border-radius: var(--radius-control, 7px);
  background: var(--primary);
  display: flex; align-items: center; justify-content: center;
  color: var(--surface);
  flex-shrink: 0;
}

.logo-text {
  display: flex; flex-direction: column; gap: 0;
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
  padding: 12px 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  height: 46px;
  margin: 0 20px;
  padding: 0 14px;
  background: transparent;
  border: none;
  border-radius: var(--radius-card, 12px);
  color: var(--text-secondary);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  font-weight: 500;
  width: auto;
  text-align: left;
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
  text-transform: none;
  letter-spacing: 0;
}

.nav-item:hover {
  background: var(--primary-light);
  color: var(--primary);
}

.nav-item.active {
  background: var(--primary-light);
  color: var(--primary);
  font-weight: 600;
}

.nav-icon {
  display: flex; align-items: center; justify-content: center;
  width: 20px; height: 20px;
  flex-shrink: 0;
  color: currentColor;
}

.nav-text {
  font-size: var(--text-sm);
  font-weight: inherit;
  line-height: 1.3;
  color: inherit;
  white-space: nowrap;
}

/* ── 折叠态 ─────────────────────────────────────────────────────── */
.sidebar.collapsed .nav { padding: 12px 0; }
.sidebar.collapsed .nav-item {
  justify-content: center;
  height: 46px;
  width: 46px;
  margin: 2px auto;
  padding: 0;
  gap: 0;
}

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
  border-radius: var(--radius-card, 12px);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
  text-transform: none;
  font-weight: 500;
}
.collapse-btn:hover {
  background: var(--surface-raised);
  color: var(--ink);
}

.collapse-arrow {
  display: inline-flex;
  transition: transform var(--duration-normal) var(--ease-out);
}
.collapse-arrow.is-collapsed { transform: rotate(180deg); }

.collapse-text {
  font-size: var(--text-xs);
  letter-spacing: 0.02em;
}

.sidebar.collapsed .collapse-btn { padding: 8px 0; }

/* ── ≤1199px：强制 64px 折叠图标栏（769–1199 与移动端一致） ───────── */
@media (max-width: 1199px) {
  .sidebar { width: var(--sidebar-collapsed-width, 64px); }
  .logo { justify-content: center; padding: 16px 0; }
  .logo-text,
  .nav-text,
  .collapse-text { display: none; }
  .nav { padding: 12px 0; }
  .nav-item { justify-content: center; height: 46px; width: 46px; margin: 2px auto; padding: 0; gap: 0; }
}

/* ── ≤767.98px（含 768 的 sub-pixel 视口）：隐藏折叠控件 ───────────── */
@media (max-width: 767.98px) {
  /* 移动端侧栏固定为图标形态，折叠控件无实际效果，隐藏避免误导 */
  .collapse-btn { display: none; }
}
</style>
