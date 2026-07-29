import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI } from '../api/auth.js'
import { beginAuthRefresh } from '../api/authRefreshCoordinator.js'

function safeGetJSON(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch { return fallback }
}

function safeSetItem(key, value) {
  try { localStorage.setItem(key, value) } catch { /* quota exceeded */ }
}

export const useAuthStore = defineStore('auth', () => {
  // 启动时清除旧 localStorage 中可能存在的 token（迁移到 HttpOnly Cookie）
  ;(function _clearLegacyTokens() {
    try {
      if (localStorage.getItem('access_token')) localStorage.removeItem('access_token')
      if (localStorage.getItem('refresh_token')) localStorage.removeItem('refresh_token')
    } catch { /* private browsing */ }
  })()

  // Access token 仅存 Pinia 内存（安全：浏览器关闭即清除）
  const accessToken = ref('')
  // User 信息可存 localStorage 用于 UI 显示（不含敏感 token）
  const user = ref(safeGetJSON('user'))
  const isRefreshing = ref(false)
  // 每次登录/退出都会推进代际，用于丢弃旧会话中迟到的刷新响应。
  const sessionGeneration = ref(0)

  const isAuthenticated = computed(() => !!accessToken.value)
  const role = computed(() => user.value?.role || '')
  const isAdmin = computed(() => role.value === 'admin')
  const isTeacher = computed(() => role.value === 'teacher')
  const isStudent = computed(() => role.value === 'student')
  const isDeveloper = computed(() => role.value === 'developer')

  function setAccessToken(token) {
    accessToken.value = token
  }

  function setUser(u) {
    user.value = u
    if (u) safeSetItem('user', JSON.stringify(u))
    else localStorage.removeItem('user')
  }

  async function login(username, password) {
    const res = await authAPI.login(username, password)
    const data = res.data
    if (!data.access_token) {
      throw new Error('登录响应缺少 access_token')
    }
    sessionGeneration.value += 1
    // Access token 仅存内存，refresh token 已在 HttpOnly Cookie
    setAccessToken(data.access_token)
    setUser(data.user || null)
    return data.user
  }

  /** 页面刷新时通过 cookie 恢复登录 */
  async function tryRestoreSession() {
    if (accessToken.value) return true  // 已有有效 token
    if (isRefreshing.value) return false

    isRefreshing.value = true
    const restoreGeneration = sessionGeneration.value
    const finishSessionRestore = beginAuthRefresh()
    try {
      const res = await authAPI.refresh()
      if (sessionGeneration.value !== restoreGeneration) {
        // 退出期间服务端可能刚轮换 Cookie；使用迟到响应中的 token 再清理一次。
        await authAPI.logout(res.data.access_token).catch(() => {})
        return false
      }
      setAccessToken(res.data.access_token)
      if (res.data.user) setUser(res.data.user)
      else await fetchMe()
      return true
    } catch {
      // Cookie 中没有有效 refresh token
      return false
    } finally {
      isRefreshing.value = false
      finishSessionRestore()
    }
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
    const token = accessToken.value
    const request = authAPI.logout(token).catch(() => {})
    sessionGeneration.value += 1
    accessToken.value = ''
    user.value = null
    localStorage.removeItem('user')
    return request
  }

  return {
    accessToken, user, isRefreshing, sessionGeneration,
    isAuthenticated, role, isAdmin, isTeacher, isStudent, isDeveloper,
    setAccessToken, setUser, login, tryRestoreSession, fetchMe, logout,
  }
})
