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
    { path: '/student/courses', label: '课程列表', icon: '' },
    { path: '/student/assignments', label: '我的作业', icon: '' },
    { path: '/student/exams', label: '考试中心', icon: '' },
    { path: '/student/experiments', label: '实验模块', icon: '' },
  ]
  if (auth.isTeacher) return [
    { path: '/teacher/courses', label: '课程管理', icon: '' },
    { path: '/teacher/assignments', label: '作业管理', icon: '' },
    { path: '/teacher/exams', label: '考试管理', icon: '' },
  ]
  if (auth.isAdmin) return [
    { path: '/admin/users', label: '用户管理', icon: '' },
    { path: '/admin/courses', label: '课程管理', icon: '' },
    { path: '/admin/experiments', label: '实验模块', icon: '' },
  ]
  return []
})

function isActive(path) {
  return route.path.startsWith(path)
}

function navigate(path) {
  router.push(path)
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed: app.sidebarCollapsed }">
    <div class="sidebar-brand" @click="navigate(menuItems[0]?.path || '/')">
      <span class="brand-icon">DAI</span>
      <span class="brand-text" v-if="!app.sidebarCollapsed">实验平台</span>
    </div>

    <nav class="sidebar-nav">
      <button
        v-for="item in menuItems" :key="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
        @click="navigate(item.path)"
      >
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-label" v-if="!app.sidebarCollapsed">{{ item.label }}</span>
      </button>
    </nav>

    <div class="sidebar-footer">
      <button class="collapse-btn" @click="app.toggleSidebar()">
        {{ app.sidebarCollapsed ? '>' : '<' }}
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed; left: 0; top: 0; bottom: 0; width: 240px;
  background: var(--bg-sidebar); color: var(--text-sidebar);
  display: flex; flex-direction: column; z-index: 100;
  transition: width 0.2s;
}
.sidebar.collapsed { width: 64px; }

.sidebar-brand {
  display: flex; align-items: center; gap: 10px; padding: 20px 18px;
  cursor: pointer; border-bottom: 1px solid rgba(255,255,255,0.08);
}
.brand-icon {
  font-size: 18px; font-weight: 700; color: #fff;
  background: var(--accent); width: 36px; height: 36px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 6px; flex-shrink: 0;
}
.brand-text { font-size: 16px; font-weight: 600; color: #fff; white-space: nowrap; }

.sidebar-nav { flex: 1; padding: 12px 8px; display: flex; flex-direction: column; gap: 2px; }

.nav-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 12px;
  background: none; border: none; color: var(--text-sidebar);
  font-size: 14px; border-radius: 6px; width: 100%; text-align: left;
  cursor: pointer; transition: background 0.15s;
}
.nav-item:hover { background: rgba(255,255,255,0.06); }
.nav-item.active { background: var(--accent); color: #fff; }
.nav-icon { font-size: 16px; flex-shrink: 0; width: 24px; text-align: center; }
.nav-label { white-space: nowrap; }

.sidebar-footer { padding: 12px; border-top: 1px solid rgba(255,255,255,0.08); }
.collapse-btn {
  width: 100%; background: rgba(255,255,255,0.05); border: none;
  color: var(--text-sidebar); font-size: 12px; padding: 6px;
  border-radius: 4px; cursor: pointer;
}
.collapse-btn:hover { background: rgba(255,255,255,0.1); }
</style>
