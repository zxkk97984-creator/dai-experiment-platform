import axios from 'axios'
import { useAuthStore } from '../stores/auth.js'
import router from '../router/index.js'

const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
  withCredentials: true,  // 发送 HttpOnly refresh cookie
})

// Request interceptor: attach access token from memory
client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

// Response interceptor: handle 401 → cookie refresh → retry
let isRefreshing = false
let refreshQueue = []

function resolveQueue(token) {
  refreshQueue.forEach(({ resolve }) => resolve(token))
  refreshQueue = []
}

function rejectQueue(error) {
  refreshQueue.forEach(({ reject }) => reject(error))
  refreshQueue = []
}

client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const { config, response } = error
    if (
      !response ||
      response.status !== 401 ||
      config?._retry ||
      config?.skipAuthRefresh
    ) {
      return Promise.reject(error)
    }

    const auth = useAuthStore()
    if (!auth.isAuthenticated) {
      router.push('/login')
      return Promise.reject(error)
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        refreshQueue.push({ resolve, reject, config })
      }).then((token) => {
        config.headers.Authorization = `Bearer ${token}`
        config._retry = true
        return client(config)
      })
    }

    isRefreshing = true
    config._retry = true
    const refreshGeneration = auth.sessionGeneration

    try {
      // Refresh via cookie（不需要手动传 refresh_token）
      const res = await axios.post('/api/v1/auth/refresh', {},
        { timeout: 10000, withCredentials: true },
      )

      const newToken = res.data.access_token
      if (
        auth.sessionGeneration !== refreshGeneration ||
        !auth.isAuthenticated
      ) {
        // 手动退出与 refresh 并发时，响应 Cookie 可能已被轮换。
        // 丢弃 access token，并用它发起幂等 logout 清理旋转后的 Cookie。
        await axios.post('/api/v1/auth/logout', {}, {
          timeout: 10000,
          withCredentials: true,
          headers: { Authorization: `Bearer ${newToken}` },
        }).catch(() => {})
        const sessionChangedError = new Error('会话已改变，已丢弃迟到的刷新结果')
        rejectQueue(sessionChangedError)
        return Promise.reject(sessionChangedError)
      }
      // 更新 Pinia 内存中的 token
      auth.setAccessToken(newToken)

      resolveQueue(newToken)
      config.headers.Authorization = `Bearer ${newToken}`
      return client(config)
    } catch (refreshError) {
      if (refreshError.response?.status === 401) {
        rejectQueue(refreshError)
        if (
          auth.sessionGeneration === refreshGeneration &&
          auth.isAuthenticated
        ) {
          auth.logout()
        }
        router.push('/login')
      } else {
        rejectQueue(refreshError)
        isRefreshing = false
      }
      return Promise.reject(error)
    } finally {
      isRefreshing = false
    }
  }
)

export default client
