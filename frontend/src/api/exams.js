import client from './client.js'

export const examsAPI = {
  list(params) { return client.get('/exams', { params }) },
  create(data) { return client.post('/exams', data) },
  get(id) { return client.get(`/exams/${id}`) },
  update(id, data) { return client.patch(`/exams/${id}`, data) },
  start(id) { return client.post(`/exams/${id}/start`) },
  submit(id, data) { return client.post(`/exams/${id}/submit`, data) },
  getGrades(id) { return client.get(`/exams/${id}/grades`) },
}
