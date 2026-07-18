<script setup>
import { useAppStore } from './stores/app.js'

const app = useAppStore()
</script>

<template>
  <div class="toast" v-if="app.toastMessage" :class="'toast-' + app.toastType">
    {{ app.toastMessage }}
  </div>
  <RouterView />
</template>

<style scoped>
.toast {
  position: fixed; top: var(--space-4); right: var(--space-4); z-index: 9999;
  padding: 10px 20px; border-radius: var(--radius-md); font-size: var(--text-sm);
  border: 1px solid; font-weight: 500;
  animation: toastIn var(--duration-normal) var(--ease-out);
  box-shadow: var(--shadow-lg);
}
.toast-success { background: var(--success-light); color: #064E3A; border-color: #8DDBC6; }
.toast-error   { background: var(--danger-light);  color: #8B1A25; border-color: #F5A3AB; }
.toast-info    { background: var(--accent-light);   color: #0F3E5C; border-color: #A3C8E0; }
@keyframes toastIn {
  from { transform: translateY(-8px); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
}
</style>
