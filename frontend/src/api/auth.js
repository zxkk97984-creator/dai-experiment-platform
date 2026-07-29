import client from './client.js'

export const authAPI = {
  login(username, password) {
    return client.post(
      '/auth/login',
      { username, password },
      { skipAuthRefresh: true },
    )
  },
  /** Refresh via HttpOnly cookie — no token in body needed */
  refresh() {
    return client.post('/auth/refresh', {}, { skipAuthRefresh: true })
  },
  /** Logout — cookie cleared by server */
  logout() {
    return client.post('/auth/logout', {}, { skipAuthRefresh: true })
  },
  me() { return client.get('/auth/me') },
}
