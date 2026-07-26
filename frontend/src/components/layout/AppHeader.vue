<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'
import { statusBadge, ROLE_MAP } from '../../utils/status.js'

const router = useRouter()
const auth = useAuthStore()

function handleLogout() {
  auth.logout()
  router.push('/login')
}

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6)  return '夜深了'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const roleBadge = computed(() => statusBadge(ROLE_MAP, auth.role))
</script>

<template>
  <header class="header">
    <div class="header-left">
      <span class="header-user">{{ auth.user?.real_name || auth.user?.username || '同学' }}</span>
    </div>

    <div class="header-right">
      <div class="user-block">
        <div class="user-avatar" aria-hidden="true">
          {{ (auth.user?.real_name || auth.user?.username || '?').charAt(0) }}
        </div>
        <button class="btn-ghost btn-sm logout-btn" @click="handleLogout" title="退出登录">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M10 3l-5 5 5 5 M5 8h9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 32px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  height: 52px;
  flex-shrink: 0;
}

/* ── User name ─────────────────────────────────────────────────────── */
.header-user {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

/* ── Right ─────────────────────────────────────────────────────────── */
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* User block */
.user-block {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
}
.user-avatar {
  width: 32px; height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
  color: #FFFFFF;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  letter-spacing: -0.01em;
}
.logout-btn {
  width: 32px; height: 32px;
  padding: 0;
  border-radius: 50%;
  color: var(--text-secondary);
}
.logout-btn:hover {
  background: var(--danger-light);
  color: var(--danger);
  border-color: transparent;
}

@media (max-width: 768px) {
  .header { padding: 0 16px; }
}
</style>
