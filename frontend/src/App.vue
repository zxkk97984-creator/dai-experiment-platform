<script setup>
import { useAppStore } from './stores/app.js'

const app = useAppStore()

const toastIcon = {
  success: '✅',
  error: '⚠️',
  info: 'ℹ️',
  warning: '🔔',
}
</script>

<template>
  <Transition name="toast">
    <div
      v-if="app.toastMessage"
      class="toast"
      :class="'toast-' + app.toastType"
      role="status"
      aria-live="polite"
    >
      <span class="toast-icon" aria-hidden="true">{{ toastIcon[app.toastType] || '💬' }}</span>
      <span class="toast-text">{{ app.toastMessage }}</span>
    </div>
  </Transition>
  <RouterView />
</template>

<style scoped>
.toast {
  position: fixed; top: 20px; right: 24px; z-index: 9999;
  display: flex; align-items: center; gap: 12px;
  padding: 14px 18px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 4px solid var(--primary);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-family: var(--font-body);
  color: var(--ink);
  font-weight: 500;
  box-shadow: var(--shadow-lg);
  max-width: 380px;
  letter-spacing: -0.005em;
}

.toast-icon {
  font-size: 16px;
  line-height: 1;
  flex-shrink: 0;
}

.toast-text { line-height: 1.45; flex: 1; min-width: 0; }

/* Type variants */
.toast-success { border-left-color: var(--success); }
.toast-error   { border-left-color: var(--danger); }
.toast-info    { border-left-color: var(--info); }
.toast-warning { border-left-color: var(--warning); }

/* Transition */
.toast-enter-active { transition: all var(--duration-normal) var(--ease-out); }
.toast-leave-active { transition: all var(--duration-fast) var(--ease-out); }
.toast-enter-from { opacity: 0; transform: translateX(24px); }
.toast-leave-to { opacity: 0; transform: translateX(24px); }
</style>
