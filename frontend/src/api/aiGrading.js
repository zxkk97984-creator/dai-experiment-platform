import client from './client.js'

export const aiGradingAPI = {
  getConfig(kind, id) { return client.get(`/ai-grading/questions/${kind}/${id}/config`) },
  updateConfig(kind, id, data) { return client.put(`/ai-grading/questions/${kind}/${id}/config`, data) },
  listRubrics(kind, id) { return client.get(`/ai-grading/questions/${kind}/${id}/rubrics`) },
  generateRubric(kind, id) { return client.post(`/ai-grading/questions/${kind}/${id}/rubrics/generate`) },
  updateRubric(id, data) { return client.patch(`/ai-grading/rubrics/${id}`, data) },
  lockRubric(id) { return client.post(`/ai-grading/rubrics/${id}/lock`) },
  listGrades(params) { return client.get('/ai-grading/grades', { params }) },
  getGrade(id) { return client.get(`/ai-grading/grades/${id}`) },
  retryGrade(id) { return client.post(`/ai-grading/grades/${id}/retry`) },
  overrideGrade(id, data) { return client.post(`/ai-grading/grades/${id}/override`, data) },
  regradeQuestion(kind, questionId) { return client.post(`/ai-grading/questions/${kind}/${questionId}/regrade`) },
}
