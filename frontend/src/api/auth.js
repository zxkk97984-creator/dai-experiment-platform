import client from './client.js'
import {
  trackAuthLogout,
  trackAuthRefresh,
  waitForAuthTransitions,
} from './authRefreshCoordinator.js'

export const authAPI = {
  async login(username, password) {
    // 避免旧 refresh/logout 的迟到 Set-Cookie 覆盖刚建立的新会话。
    await waitForAuthTransitions()
    return client.post(
      '/auth/login',
      { username, password },
      { skipAuthRefresh: true },
    )
  },
  /** Refresh via HttpOnly cookie — no token in body needed */
  refresh() {
    return trackAuthRefresh(
      client.post('/auth/refresh', {}, { skipAuthRefresh: true }),
    )
  },
  /** Logout — cookie cleared by server */
  logout(accessToken = '') {
    const config = { skipAuthRefresh: true }
    if (accessToken) {
      config.headers = { Authorization: `Bearer ${accessToken}` }
    }
    return trackAuthLogout(client.post('/auth/logout', {}, config))
  },
  me() { return client.get('/auth/me') },
}
