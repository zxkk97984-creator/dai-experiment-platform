<script setup>
import AppIcon from './components/ui/AppIcon.vue'
import { useAppStore } from './stores/app.js'

const app = useAppStore()

const toastIcon = {
  success: 'check',
  error: 'close',
  info: 'notification',
  warning: 'warning',
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
      <span class="toast-icon" aria-hidden="true">
        <AppIcon :name="toastIcon[app.toastType] || 'notification'" :size="16" />
      </span>
      <span class="toast-text">{{ app.toastMessage }}</span>
    </div>
  </Transition>
  <RouterView />
</template>

<style scoped>
/* Toast 为 V2 扩展组件：token-only，左 3px 语义栏；无类型时使用 accent。 */
.toast {
  position: fixed;
  top: 20px;
  right: 24px;
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius-lg);
  font-size: var(--text-md);
  font-family: var(--font-body);
  color: var(--fg);
  font-weight: 500;
  box-shadow: var(--shadow-lg);
  max-width: 380px;
  letter-spacing: -0.005em;
}

.toast-icon {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  color: var(--accent);
}

.toast-success .toast-icon { color: var(--success); }
.toast-error   .toast-icon { color: var(--danger); }
.toast-info    .toast-icon { color: var(--info); }
.toast-warning .toast-icon { color: var(--warning); }

.toast-success { border-left-color: var(--success); }
.toast-error   { border-left-color: var(--danger); }
.toast-info    { border-left-color: var(--info); }
.toast-warning { border-left-color: var(--warning); }

.toast-text { line-height: 1.45; flex: 1; min-width: 0; }

.toast-enter-active { transition: all var(--duration-normal, 220ms) var(--ease-out, ease); }
.toast-leave-active { transition: all var(--duration-fast, 120ms) var(--ease-out, ease); }
.toast-enter-from { opacity: 0; transform: translateX(24px); }
.toast-leave-to { opacity: 0; transform: translateX(24px); }
</style>
