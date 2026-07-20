<script setup>
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
import { useAppStore } from '../../stores/app.js'

const app = useAppStore()
</script>

<template>
  <div class="layout">
    <AppSidebar />
    <div class="main-area" :class="{ collapsed: app.sidebarCollapsed }">
      <AppHeader />
      <main class="content">
        <div class="content-inner">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--paper);
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-left: 240px;
  transition: margin-left var(--duration-slow) var(--ease-out);
  min-width: 0;
  background: var(--paper);
}
.main-area.collapsed { margin-left: 64px; }

.content {
  flex: 1;
  overflow-y: auto;
  background: var(--paper);
}

.content-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 32px 40px 80px;
}

@media (max-width: 768px) {
  .content-inner { padding: 20px 16px 60px; }
}
</style>
