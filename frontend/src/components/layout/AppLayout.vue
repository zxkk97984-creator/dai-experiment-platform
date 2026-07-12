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
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout { display: flex; height: 100vh; overflow: hidden; }
.main-area { flex: 1; display: flex; flex-direction: column; margin-left: 240px; transition: margin-left 0.2s; min-width: 0; }
.main-area.collapsed { margin-left: 64px; }
.content { flex: 1; overflow-y: auto; padding: 24px; }
</style>
