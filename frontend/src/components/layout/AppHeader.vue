<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'
import { statusBadge, ROLE_MAP } from '../../utils/status.js'

const router = useRouter()
const auth = useAuthStore()

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <header class="header">
    <div class="header-left">
      <span class="header-role">
        {{ statusBadge(ROLE_MAP, auth.role).label }}端
      </span>
    </div>
    <div class="header-right">
      <span class="user-name">{{ auth.user?.real_name || auth.user?.username }}</span>
      <span class="user-role badge" :class="'badge-' + statusBadge(ROLE_MAP, auth.role).color">
        {{ statusBadge(ROLE_MAP, auth.role).label }}
      </span>
      <button class="btn-ghost btn-sm" @click="handleLogout">退出登录</button>
    </div>
  </header>
</template>

<style scoped>
.header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 var(--space-6);
  background: var(--bg-header);
  border-bottom: 1px solid var(--border);
  height: 52px; flex-shrink: 0;
}
.header-left { display: flex; align-items: center; }
.header-role {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--text-secondary);
  letter-spacing: 0.04em;
}
.header-right { display: flex; align-items: center; gap: 10px; }
.user-name {
  font-weight: 500;
  font-size: var(--text-sm);
  color: var(--text);
}
</style>
