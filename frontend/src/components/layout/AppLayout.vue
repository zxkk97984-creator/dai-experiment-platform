<script setup>
import { onMounted } from 'vue'
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
import { useAppStore } from '../../stores/app.js'
import { useAuthStore } from '../../stores/auth.js'
import { usersAPI } from '../../api/users.js'

const app = useAppStore()
const auth = useAuthStore()

onMounted(async () => {
  if (!auth.isAuthenticated) return
  try {
    const { data } = await usersAPI.getMyPreferences()
    const prefs = data?.preferences || {}
    if (typeof prefs.sidebar_collapsed === 'boolean') {
      app.sidebarCollapsed = prefs.sidebar_collapsed
    }
  } catch {
    // 偏好加载失败时保留本地状态
  }
})
</script>

<template>
  <div
    class="shell"
    :class="{ 'is-collapsed': app.sidebarCollapsed, 'mobile-nav-open': app.mobileNavOpen }"
  >
    <AppSidebar />
    <div class="main">
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
/* App Shell 视觉与断点全部来自全局 dai-ds-v2.css 的 .shell/.sidebar/.main/.content。
   组件内不再重复定义宽度、高度、断点或固定侧栏 margin。 */
</style>
