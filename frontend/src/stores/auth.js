import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI } from '../api/auth.js'

function safeGetJSON(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch { return fallback }
}

function safeSetItem(key, value) {
  try { localStorage.setItem(key, value) } catch { /* quota exceeded or private browsing */ }
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const user = ref(safeGetJSON('user'))

  const isLoggedIn = computed(() => !!accessToken.value)
  const role = computed(() => user.value?.role || '')
  const isAdmin = computed(() => role.value === 'admin')
  const isTeacher = computed(() => role.value === 'teacher')
  const isStudent = computed(() => role.value === 'student')

  function setTokens(access, refresh) {
    accessToken.value = access
    refreshToken.value = refresh
    safeSetItem('access_token', access)
    if (refresh) safeSetItem('refresh_token', refresh)
  }

  function setUser(u) {
    user.value = u
    safeSetItem('user', JSON.stringify(u))
  }

  async function login(username, password) {
    const res = await authAPI.login(username, password)
    const data = res.data
    if (!data.access_token) {
      throw new Error('登录响应缺少 access_token')
    }
    setTokens(data.access_token, data.refresh_token)
    setUser(data.user || null)
    return data.user
  }

  async function fetchMe() {
    try {
      const res = await authAPI.me()
      setUser(res.data)
      return res.data
    } catch (e) {
      if (e.response?.status === 401) {
        logout()
      }
      return null
    }
  }

  function logout() {
    if (refreshToken.value) {
      authAPI.logout(refreshToken.value).catch(() => {})
    }
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
  }

  return {
    accessToken, refreshToken, user,
    isLoggedIn, role, isAdmin, isTeacher, isStudent,
    setTokens, setUser, login, fetchMe, logout,
  }
})
