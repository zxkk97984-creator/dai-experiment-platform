import client from './client.js'

export const judgeAPI = {
  submit(data) { return client.post('/judge/submissions', data) },
  list(params) { return client.get('/judge/submissions', { params }) },
  get(id) { return client.get(`/judge/submissions/${id}`) },
  getResult(id) { return client.get(`/judge/submissions/${id}/result`) },
  sampleRun(questionId, data) { return client.post(`/judge/questions/${questionId}/sample-run`, data) },
}
