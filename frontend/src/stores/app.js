import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(localStorage.getItem('dai.sidebarCollapsed') === '1')
  const mobileNavOpen = ref(false)
  const toastMessage = ref('')
  const toastType = ref('info')

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    try { localStorage.setItem('dai.sidebarCollapsed', sidebarCollapsed.value ? '1' : '0') } catch { /* ignore */ }
  }

  function openMobileNav() { mobileNavOpen.value = true }
  function closeMobileNav() { mobileNavOpen.value = false }
  function toggleMobileNav() { mobileNavOpen.value = !mobileNavOpen.value }

  function showToast(msg, type = 'info') {
    toastMessage.value = msg
    toastType.value = type
    setTimeout(() => { toastMessage.value = '' }, 3000)
  }

  return {
    sidebarCollapsed, mobileNavOpen,
    toastMessage, toastType,
    toggleSidebar, openMobileNav, closeMobileNav, toggleMobileNav,
    showToast,
  }
})
