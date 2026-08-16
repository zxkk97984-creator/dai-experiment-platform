import client from './client.js'

export const notificationsAPI = {
  list(params) {
    return client.get('/notifications', { params })
  },
  markRead(id) {
    return client.post(`/notifications/${id}/read`)
  },
  markAllRead() {
    return client.post('/notifications/read-all')
  },
}
