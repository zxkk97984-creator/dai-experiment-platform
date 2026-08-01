import client from './client.js'

export const announcementsAPI = {
  create(payload) {
    return client.post('/announcements', payload)
  },
  markRead(id) {
    return client.post(`/announcements/${id}/read`)
  },
}
