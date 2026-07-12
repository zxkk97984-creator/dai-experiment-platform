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
  position: fixed; top: 16px; right: 16px; z-index: 9999;
  padding: 10px 20px; border-radius: 6px; font-size: 14px;
  border: 1px solid; animation: slideIn 0.2s ease;
}
.toast-success { background: #d1fae5; color: #065f46; border-color: #6ee7b7; }
.toast-error { background: #fee2e2; color: #991b1b; border-color: #fca5a5; }
.toast-info { background: #dbeafe; color: #1e40af; border-color: #93c5fd; }
@keyframes slideIn { from { transform: translateY(-10px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
</style>
