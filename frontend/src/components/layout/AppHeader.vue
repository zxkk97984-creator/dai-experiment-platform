<script setup>
// AppHeader：右侧单一用户菜单触发器（姓名 + 圆形头像 + chevron）。
// 菜单键盘可访问（TASK-024）：打开后焦点移入首个菜单项；
// Escape / 外部点击关闭后焦点恢复到触发器；Tab/Enter/Space 保持原生行为。

import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from '../ui/AppIcon.vue'
import { useAuthStore } from '../../stores/auth.js'
import { ROLE_MAP, statusBadge } from '../../utils/status.js'

const router = useRouter()
const auth = useAuthStore()

const open = ref(false)
const wrapEl = ref(null)
const triggerEl = ref(null)
const menuEl = ref(null)

const displayName = computed(() => auth.user?.real_name || auth.user?.username || '同学')
const roleBadge = computed(() => statusBadge(ROLE_MAP, auth.role))

function openMenu() {
  open.value = true
  // 焦点移入菜单首个可操作项，读屏/键盘用户立即进入菜单上下文
  nextTick(() => {
    const first = menuEl.value?.querySelector('button, [role="menuitem"]')
    first?.focus()
  })
}

function close() {
  if (!open.value) return
  open.value = false
  // Escape / 外部点击 / 退出动作后焦点恢复到触发器
  nextTick(() => triggerEl.value?.focus())
}

function toggle() { open.value ? close() : openMenu() }

// Escape 关闭（菜单内任意焦点位置均冒泡到 header 根）
function onKeydown(e) {
  if (e.key === 'Escape') close()
}

// 外部点击关闭；触发器自身内部的点击由 toggle 接管
function onDocPointerDown(e) {
  if (wrapEl.value && wrapEl.value.contains(e.target)) return
  close()
}

function handleLogout() {
  close()
  auth.logout()
  router.push('/login')
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocPointerDown)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocPointerDown)
})
</script>

<template>
  <header class="header" @keydown="onKeydown">
    <div class="header-left"></div>

    <div class="header-right">
      <div ref="wrapEl" class="user-menu-wrap">
        <button
          ref="triggerEl"
          type="button"
          class="user-trigger"
          :aria-expanded="open"
          aria-haspopup="menu"
          @click="toggle"
        >
          <span class="user-name">{{ displayName }}</span>
          <span class="user-avatar" aria-hidden="true">
            <AppIcon name="user" :size="18" />
          </span>
          <span class="user-chevron" aria-hidden="true">
            <AppIcon name="chevron-down" :size="16" />
          </span>
        </button>

        <div v-if="open" ref="menuEl" class="user-menu" role="menu" aria-label="用户菜单">
          <div class="user-menu-head">
            <span class="user-menu-name">{{ displayName }}</span>
            <span class="user-menu-role">{{ roleBadge.label }}</span>
          </div>
          <div class="user-menu-sep"></div>
          <button type="button" class="user-menu-item" role="menuitem" @click="handleLogout">
            <AppIcon name="logout" :size="16" />
            <span>退出登录</span>
          </button>
        </div>
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
  height: var(--header-height, 64px);
  flex-shrink: 0;
}

.header-left { flex: 1; }

/* ── 用户触发器 ───────────────────────────────────────────────────── */
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  position: relative;
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px 6px 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              border-color var(--duration-fast) var(--ease-out);
}
.user-trigger:hover {
  background: var(--paper);
  border-color: var(--border-strong);
}

.user-name {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--ink);
  white-space: nowrap;
}

.user-avatar {
  width: 38px; height: 38px;
  border-radius: 50%;
  background: var(--surface-raised);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid var(--border);
}

.user-chevron {
  display: inline-flex;
  color: var(--text-tertiary);
  transition: transform var(--duration-fast) var(--ease-out);
}
.user-trigger[aria-expanded='true'] .user-chevron { transform: rotate(180deg); }

/* ── 下拉菜单 ─────────────────────────────────────────────────────── */
.user-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  min-width: 200px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card, 12px);
  box-shadow: 0 8px 24px rgba(31, 58, 94, 0.10);
  padding: 6px;
  z-index: 200;
}

.user-menu-head {
  padding: 10px 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.user-menu-name {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
}
.user-menu-role {
  font-size: var(--text-xs);
  color: var(--text-secondary);
}
.user-menu-sep {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}

.user-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 9px 12px;
  background: transparent;
  border: none;
  border-radius: var(--radius-control, 7px);
  color: var(--text-secondary);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              color var(--duration-fast) var(--ease-out);
}
.user-menu-item:hover {
  background: var(--danger-light);
  color: var(--danger);
}

@media (max-width: 767.98px) {
  .header { padding: 0 16px; }
  .user-name { display: none; }
}
</style>
