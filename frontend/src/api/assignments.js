import client from './client.js'

export const assignmentsAPI = {
  list(params) { return client.get('/assignments', { params }) },
  create(data) { return client.post('/assignments', data) },
  get(id) { return client.get(`/assignments/${id}`) },
  update(id, data) { return client.patch(`/assignments/${id}`, data) },
  publish(id) { return client.post(`/assignments/${id}/publish`) },
  getQuestions(assignmentId) { return client.get(`/assignments/${assignmentId}/questions`) },
  createQuestion(assignmentId, data) { return client.post(`/assignments/${assignmentId}/questions`, data) },
}
