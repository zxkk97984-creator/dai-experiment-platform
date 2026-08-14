import client from './client.js'

export const aiGradingAPI = {
  /** TASK-020：AI 服务状态（enabled=开关，ready=开关+Key 齐备） */
  getStatus() { return client.get('/ai-grading/status') },
  getConfig(kind, id) { return client.get(`/ai-grading/questions/${kind}/${id}/config`) },
  updateConfig(kind, id, data) { return client.put(`/ai-grading/questions/${kind}/${id}/config`, data) },
  listRubrics(kind, id) { return client.get(`/ai-grading/questions/${kind}/${id}/rubrics`) },
  generateRubric(kind, id) { return client.post(`/ai-grading/questions/${kind}/${id}/rubrics/generate`) },
  // 生成需两次 DeepSeek 调用 + Docker 预检（60-90s），单独设长超时，避免 axios 默认 30s 中断
  generateTestGroups(kind, id, data) { return client.post(`/ai-grading/questions/${kind}/${id}/test-groups/generate`, data, { timeout: 180000 }) },
  updateRubric(id, data) { return client.patch(`/ai-grading/rubrics/${id}`, data) },
  lockRubric(id) { return client.post(`/ai-grading/rubrics/${id}/lock`) },
  listGrades(params) { return client.get('/ai-grading/grades', { params }) },
  getGrade(id) { return client.get(`/ai-grading/grades/${id}`) },
  retryGrade(id) { return client.post(`/ai-grading/grades/${id}/retry`) },
  overrideGrade(id, data) { return client.post(`/ai-grading/grades/${id}/override`, data) },
  regradeQuestion(kind, questionId) { return client.post(`/ai-grading/questions/${kind}/${questionId}/regrade`) },
}
