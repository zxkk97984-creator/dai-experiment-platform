<script setup>
import AppLayout from '../../components/layout/AppLayout.vue'
import { useRouter } from 'vue-router'
const router = useRouter()
</script>
<template>
  <AppLayout>
    <h1 class="page-title">管理后台</h1>
    <div class="grid-3">
      <div class="card dash-card" @click="router.push('/admin/users')">
        <div class="dash-card-icon dash-icon-users">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <circle cx="8" cy="7" r="3" stroke="currentColor" stroke-width="1.4"/>
            <circle cx="15" cy="7" r="2.5" stroke="currentColor" stroke-width="1.4"/>
            <path d="M2 18c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
            <path d="M13 14c2.2.3 4 2 4 4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
          </svg>
        </div>
        <h3>用户管理</h3>
        <p>创建、编辑、管理用户账号和权限</p>
      </div>
      <div class="card dash-card" @click="router.push('/admin/courses')">
        <div class="dash-card-icon dash-icon-courses">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M3 5h6l2 3h8v9H3V5z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
          </svg>
        </div>
        <h3>课程管理</h3>
        <p>管理全部课程资源</p>
      </div>
      <div class="card dash-card" @click="router.push('/admin/experiments')">
        <div class="dash-card-icon dash-icon-lab">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <rect x="3" y="8" width="16" height="10" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
            <path d="M7 8V5.5C7 4.67 7.67 4 8.5 4h5c.83 0 1.5.67 1.5 1.5V8" stroke="currentColor" stroke-width="1.4"/>
          </svg>
        </div>
        <h3>实验模块</h3>
        <p>配置和管理实验模块</p>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ── Page title ── */
.page-title {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 400;
  color: var(--ink);
  margin-bottom: var(--space-6);
  letter-spacing: -0.01em;
  line-height: 1.2;
}

/* ── Action grid ── */
.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}

.dash-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6) var(--space-6) var(--space-5);
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}

.dash-card:hover {
  border-color: #E0553D;
  box-shadow: 0 0 16px rgba(224, 85, 61, 0.1);
  transform: translateY(-1px);
}

.dash-card:active {
  transform: scale(0.99);
}

.dash-card h3 {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: 400;
  color: var(--ink);
  margin: var(--space-4) 0 var(--space-2);
  letter-spacing: -0.01em;
}

.dash-card p {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}

/* ── Icon blocks ── */
.dash-card-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.dash-icon-users {
  background: rgba(124, 92, 252, 0.12);
  color: #7C5CFC;
}

.dash-icon-courses {
  background: rgba(59, 130, 246, 0.12);
  color: #3B82F6;
}

.dash-icon-lab {
  background: rgba(16, 185, 129, 0.12);
  color: #10B981;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .grid-3 {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1024px) {
  .grid-3 {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
