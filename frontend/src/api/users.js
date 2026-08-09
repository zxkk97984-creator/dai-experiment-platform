import client from './client.js'

export const usersAPI = {
  list(params) { return client.get('/users', { params }) },
  create(data) { return client.post('/users', data) },
  get(id) { return client.get(`/users/${id}`) },
  update(id, data) { return client.patch(`/users/${id}`, data) },
  updatePassword(id, data) { return client.patch(`/users/${id}/password`, data) },
  updateStatus(id, data) { return client.patch(`/users/${id}/status`, data) },
  listStudents(params) { return client.get('/users/students', { params }) },
}
