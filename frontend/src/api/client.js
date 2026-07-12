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

// Response interceptor: handle 401  refresh  retry
let isRefreshing = false
let refreshQueue = []

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
      return new Promise((resolve) => {
        refreshQueue.push((token) => {
          config.headers.Authorization = `Bearer ${token}`
          resolve(client(config))
        })
      })
    }

    isRefreshing = true
    config._retry = true

    try {
      const res = await axios.post('/api/v1/auth/refresh', {
        refresh_token: auth.refreshToken,
      })
      const newToken = res.data.access_token
      const newRefresh = res.data.refresh_token
      auth.setTokens(newToken, newRefresh)

      refreshQueue.forEach((cb) => cb(newToken))
      refreshQueue = []

      config.headers.Authorization = `Bearer ${newToken}`
      return client(config)
    } catch {
      refreshQueue = []
      auth.logout()
      router.push('/login')
      return Promise.reject(error)
    } finally {
      isRefreshing = false
    }
  }
)

export default client
