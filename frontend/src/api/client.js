import axios from 'axios'
import { useAuthStore } from '../stores/auth.js'
import router from '../router/index.js'

const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

// Request interceptor: attach token
client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

// Response interceptor: handle 401 → refresh → retry
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
    if (!response || response.status !== 401 || config._retry) {
      return Promise.reject(error)
    }

    const auth = useAuthStore()
    if (!auth.refreshToken) {
      auth.logout()
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

    try {
      const res = await axios.post('/api/v1/auth/refresh', {
        refresh_token: auth.refreshToken,
      }, { timeout: 10000 })

      const newToken = res.data.access_token
      const newRefresh = res.data.refresh_token
      auth.setTokens(newToken, newRefresh)

      resolveQueue(newToken)

      config.headers.Authorization = `Bearer ${newToken}`
      return client(config)
    } catch (refreshError) {
      if (refreshError.response?.status === 401) {
        rejectQueue(refreshError)
        auth.logout()
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
