<script setup>
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { useAuthStore } from '../../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()
</script>

<template>
  <AppLayout>
    <h1 class="page-title">{{ auth.user?.real_name || auth.user?.username }}，欢迎回来</h1>

    <div class="grid-3">
      <div class="card dash-card" @click="router.push('/student/courses')">
        <div class="dash-card-icon dash-icon-courses">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M3 5h6l2 3h8v9H3V5z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
            <path d="M3 18V5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
          </svg>
        </div>
        <h3>课程学习</h3>
        <p>浏览课程目录，查看章节和课时内容</p>
      </div>

      <div class="card dash-card" @click="router.push('/student/assignments')">
        <div class="dash-card-icon dash-icon-code">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M7 8l-3 3 3 3M15 8l3 3-3 3M13 5l-4 12" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <h3>作业提交</h3>
        <p>在线编写 Python 代码，提交后自动判题</p>
      </div>

      <div class="card dash-card" @click="router.push('/student/jupyter')">
        <div class="dash-card-icon dash-icon-lab">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <rect x="3" y="8" width="16" height="10" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
            <path d="M7 8V5.5C7 4.67 7.67 4 8.5 4h5c.83 0 1.5.67 1.5 1.5V8" stroke="currentColor" stroke-width="1.4"/>
            <circle cx="11" cy="13" r="1.5" fill="currentColor"/>
          </svg>
        </div>
        <h3>在线实验</h3>
        <p>通过 JupyterLab 完成交互式编程实验</p>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
/* ── Reading Room dashboard ─────────────────────────────────────── */

.page-title {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 400;
  color: var(--ink);
  margin-bottom: var(--space-8);
  letter-spacing: -0.01em;
  line-height: 1.2;
}

/* ── Action cards ──────────────────────────────────────────────────── */
.dash-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6) var(--space-6) var(--space-5);
  cursor: pointer;
  transition: border-color var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out),
              transform var(--duration-normal) var(--ease-out);
}

.dash-card:hover {
  border-color: var(--accent);
  box-shadow: 0 0 24px rgba(224, 85, 61, 0.18),
              0 4px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
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

/* ── Icon containers ───────────────────────────────────────────────── */
.dash-card-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.dash-icon-courses {
  background: rgba(59, 130, 246, 0.10);
  color: #3B82F6;
}

.dash-icon-code {
  background: rgba(224, 85, 61, 0.10);
  color: #E0553D;
}

.dash-icon-lab {
  background: rgba(16, 185, 129, 0.10);
  color: #10B981;
}
</style>
