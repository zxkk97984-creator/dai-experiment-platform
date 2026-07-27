import client from './client.js'

export const authAPI = {
  login(username, password) {
    return client.post('/auth/login', { username, password })
  },
  /** Refresh via HttpOnly cookie — no token in body needed */
  refresh() {
    return client.post('/auth/refresh', {})
  },
  /** Logout — cookie cleared by server */
  logout() {
    return client.post('/auth/logout', {})
  },
  me() { return client.get('/auth/me') },
}
