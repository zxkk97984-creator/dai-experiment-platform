import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI } from '../api/auth.js'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => !!accessToken.value)
  const role = computed(() => user.value?.role || '')
  const isAdmin = computed(() => role.value === 'admin')
  const isTeacher = computed(() => role.value === 'teacher')
  const isStudent = computed(() => role.value === 'student')

  function setTokens(access, refresh) {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem('access_token', access)
    if (refresh) localStorage.setItem('refresh_token', refresh)
  }

  function setUser(u) {
    user.value = u
    localStorage.setItem('user', JSON.stringify(u))
  }

  async function login(username, password) {
    const res = await authAPI.login(username, password)
    const data = res.data
    setTokens(data.access_token, data.refresh_token)
    setUser(data.user)
    return data.user
  }

  async function fetchMe() {
    try {
      const res = await authAPI.me()
      setUser(res.data)
      return res.data
    } catch {
      logout()
      return null
    }
  }

  function logout() {
    try {
      if (refreshToken.value) {
        authAPI.logout(refreshToken.value).catch(() => {})
      }
    } finally {
      accessToken.value = ''
      refreshToken.value = ''
      user.value = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
    }
  }

  return {
    accessToken, refreshToken, user,
    isLoggedIn, role, isAdmin, isTeacher, isStudent,
    setTokens, setUser, login, fetchMe, logout,
  }
})
