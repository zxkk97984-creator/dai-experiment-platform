import client from './client.js'

export const searchAPI = {
  global(q) {
    return client.get('/search', { params: { q } })
  },
}
