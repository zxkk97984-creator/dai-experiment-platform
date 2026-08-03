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
  margin-left: var(--sidebar-width, 264px);
  transition: margin-left var(--duration-slow) var(--ease-out);
  min-width: 0;
  background: var(--paper);
}
.main-area.collapsed { margin-left: var(--sidebar-collapsed-width, 64px); }

/* 内容区：fluid，页面自身滚动，侧栏不滚动 */
.content {
  flex: 1;
  overflow-y: auto;
  background: var(--paper);
}

.content-inner {
  max-width: var(--content-max, 1440px);
  margin: 0 auto;
  padding: 28px 36px 80px;
}

/* ≤1199px：64px 折叠侧栏 + 单列内容 */
@media (max-width: 1199px) {
  .main-area { margin-left: var(--sidebar-collapsed-width, 64px); }
}

@media (max-width: 767.98px) {
  .content-inner { padding: 20px 16px 60px; }
  .main-area { margin-left: var(--sidebar-collapsed-width, 64px); }
}
</style>
