import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const toastMessage = ref('')
  const toastType = ref('info')

  function toggleSidebar() { sidebarCollapsed.value = !sidebarCollapsed.value }

  function showToast(msg, type = 'info') {
    toastMessage.value = msg
    toastType.value = type
    setTimeout(() => { toastMessage.value = '' }, 3000)
  }

  return { sidebarCollapsed, toastMessage, toastType, toggleSidebar, showToast }
})
