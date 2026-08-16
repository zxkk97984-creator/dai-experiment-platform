<script setup>
// AppSidebar：共享认证侧栏（Design System V2）。
// 视觉遵循 dai-ds-v2.css：浅岩灰底、分组标签、36px 导航项、
// 激活态为 2px 墨松绿左栏 + accent-faint 底；底部用户卡保留真实身份信息。
// 路由、权限与菜单数据保持原业务逻辑不变。

import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'
import { useAppStore } from '../../stores/app.js'
import { homeForRole } from '../../router/roleHome.js'
import { dashboardAPI } from '../../api/dashboard.js'
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
    { path: '/teacher',                label: '工作台',     sub: 'Workbench',     icon: 'home',        key: 'home' },
    { path: '/teacher/courses',        label: '课程管理',   sub: 'Courses',       icon: 'course',      key: 'courses' },
    { path: '/teacher/assignments',    label: '作业管理',   sub: 'Assignments',   icon: 'assignment',  key: 'assignments' },
    { path: '/teacher/experiments',    label: '实验管理',   sub: 'Experiments',   icon: 'experiment',  key: 'experiments' },
    { path: '/teacher/exams',          label: '考试管理',   sub: 'Exams',         icon: 'exam',        key: 'exams' },
    { path: '/teacher/classes',        label: '班级与学员', sub: 'Classes',       icon: 'user',        key: 'classes' },
    { path: '/teacher/submissions/unified', label: '提交与评分', sub: 'Submissions', icon: 'clipboard', key: 'submissions' },
    { path: '/teacher/ai-grading',     label: 'AI 评分复核', sub: 'AI Grading',   icon: 'brain',       key: 'ai-grading' },
    { path: '/teacher/grades',         label: '成绩统计',   sub: 'Grades',        icon: 'chart',       key: 'grades' },
    { path: '/teacher/environments',   label: '运行环境',   sub: 'Environments',  icon: 'cube',        key: 'environments' },
    { path: '/teacher/settings',       label: '设置',       sub: 'Settings',      icon: 'settings',    key: 'settings' },
  ]
  if (auth.isAdmin) return [
    { path: '/admin/users',         label: '用户管理', sub: 'Users',       icon: 'user',       key: 'users' },
    { path: '/admin/academics',     label: '教务管理', sub: 'Academics',   icon: 'course',     key: 'academics' },
    { path: '/admin/courses',       label: '课程管理', sub: 'Courses',     icon: 'course',     key: 'courses' },
    { path: '/admin/experiments',   label: '实验管理', sub: 'Experiments', icon: 'experiment', key: 'experiments' },
    { path: '/admin/environments',  label: '环境档位', sub: 'Environments', icon: 'experiment', key: 'environments' },
    { path: '/admin/ai-grading',    label: 'AI 评分复核', sub: 'AI Grading', icon: 'brain',      key: 'ai-grading' },
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

// 侧栏分组：视觉按 V2「分组标签 + 组间距」；菜单数据与权限仍来自 menuItems
const navGroups = computed(() => {
  const items = menuItems.value
  const pick = (keys) => items.filter((item) => keys.includes(item.key))
  if (auth.isTeacher) {
    return [
      { label: '教学', items: pick(['home', 'courses', 'assignments', 'experiments', 'exams', 'classes']) },
      { label: '评分', items: pick(['submissions', 'ai-grading', 'grades']) },
      { label: '系统', items: pick(['environments', 'settings']) },
    ]
  }
  if (auth.isAdmin) {
    return [
      { label: '教务', items: pick(['users', 'academics', 'courses', 'experiments']) },
      { label: '评分', items: pick(['ai-grading']) },
      { label: '系统', items: pick(['environments']) },
    ]
  }
  if (auth.isDeveloper) return [{ label: '开发', items }]
  return [{ label: '学习', items }]
})

const displayName = computed(() => auth.user?.real_name || auth.user?.username || '同学')
const avatarText = computed(() => displayName.value.trim().slice(0, 1))
const roleText = computed(() => {
  const map = { student: '学生', teacher: '教师', admin: '管理员', developer: '开发者' }
  const role = map[auth.role] || auth.role || ''
  if (auth.role === 'teacher' && auth.user?.department) return `${role} · ${auth.user.department}`
  return role
})

const teacherCounts = ref({ pending_grading_count: 0, pending_review_count: 0 })
let countsTimer = null

async function loadTeacherCounts() {
  if (!auth.isTeacher) return
  try {
    const { data } = await dashboardAPI.teacherCounts()
    teacherCounts.value = data
  } catch {
    // 徽标加载失败静默，不阻塞导航
  }
}

function submissionBadge() {
  if (!auth.isTeacher) return 0
  return Number(teacherCounts.value.pending_grading_count || 0)
}

onMounted(() => {
  loadTeacherCounts()
  if (auth.isTeacher) countsTimer = window.setInterval(loadTeacherCounts, 60000)
})
onBeforeUnmount(() => {
  if (countsTimer) window.clearInterval(countsTimer)
})

function isActive(path) {
  if (path === '/student/assignments' && route.path.startsWith('/student/submissions')) return true
  if (path === '/teacher/submissions/unified' && route.path.startsWith('/teacher/submissions')) return true
  if (path === '/admin/submissions' && route.path.startsWith('/admin/submissions')) return true
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
    <button
      type="button"
      class="logo sidebar-head"
      aria-label="返回首页"
      @click="navigate(homeForRole(auth.role))"
    >
      <span class="wordmark"><span class="mark">DAI</span><small>实验平台</small></span>
    </button>

    <nav class="sidebar-nav">
      <div v-for="group in navGroups" :key="group.label" class="nav-group">
        <div class="nav-label">{{ group.label }}</div>
        <button
          v-for="item in group.items"
          :key="item.path"
          type="button"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
          :aria-label="item.label"
          :aria-current="isActive(item.path) ? 'page' : undefined"
          :title="app.sidebarCollapsed ? item.label : undefined"
          @click="navigate(item.path)"
        >
          <AppIcon :name="item.icon" :size="17" aria-hidden="true" />
          <span class="nav-text">{{ item.label }}</span>
          <span v-if="item.key === 'submissions' && submissionBadge() > 0" class="nav-badge">{{ submissionBadge() }}</span>
        </button>
      </div>
    </nav>

    <div class="sidebar-foot">
      <div class="user-card">
        <span class="avatar" aria-hidden="true">{{ avatarText }}</span>
        <div class="grow">
          <div class="u-name">{{ displayName }}</div>
          <div class="u-role">{{ roleText }}</div>
        </div>
      </div>
      <button
        class="collapse-btn"
        type="button"
        @click="app.toggleSidebar()"
        :title="app.sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
        :aria-label="app.sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
      >
        <AppIcon :name="app.sidebarCollapsed ? 'chevron-right' : 'back'" :size="15" aria-hidden="true" />
        <span class="collapse-text">收起</span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
/* 全部可复用视觉来自全局 dai-ds-v2.css；
   此处只保留组件内组合所需的局部结构，不新增颜色 / 圆角 / 字号。 */
.logo {
  width: 100%;
  border: 0;
  background: transparent;
  justify-content: flex-start;
  text-align: left;
}
.logo:hover { background: transparent; border-color: transparent; }
.nav-item { width: auto; margin: 2px 0 0; border: 0; background: transparent; }
.sidebar-foot { display: flex; flex-direction: column; gap: var(--space-1); }
.collapse-btn {
  width: 100%;
  justify-content: center;
  color: var(--faint);
  background: transparent;
  border-color: transparent;
  font-size: var(--text-sm);
}
.collapse-btn:hover { color: var(--fg); background: var(--surface-sunken); border-color: transparent; }
.collapse-text { font-size: var(--text-xs); letter-spacing: 0.02em; }
</style>
