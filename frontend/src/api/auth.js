import client from './client.js'

export const authAPI = {
  login(username, password) { return client.post('/auth/login', { username, password }) },
  refresh(refreshToken) { return client.post('/auth/refresh', { refresh_token: refreshToken }) },
  logout(refreshToken) { return client.post('/auth/logout', { refresh_token: refreshToken }) },
  me() { return client.get('/auth/me') },
}
