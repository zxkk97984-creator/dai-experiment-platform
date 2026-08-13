import client from './client.js'

export const assignmentsAPI = {
  list(params) { return client.get('/assignments', { params }) },
  create(data) { return client.post('/assignments', data) },
  get(id) { return client.get(`/assignments/${id}`) },
  update(id, data) { return client.patch(`/assignments/${id}`, data) },
  publish(id) { return client.post(`/assignments/${id}/publish`) },
  deleteAssignment(id) { return client.delete(`/assignments/${id}`) },
  unpublishAssignment(id) { return client.post(`/assignments/${id}/unpublish`) },
  getQuestions(assignmentId) { return client.get(`/assignments/${assignmentId}/questions`) },
  createQuestion(assignmentId, data) { return client.post(`/assignments/${assignmentId}/questions`, data) },
  // Phase 4：题目编辑（环境覆盖/import 策略在 QuestionEditView 使用）
  updateQuestion(assignmentId, questionId, data) { return client.patch(`/assignments/${assignmentId}/questions/${questionId}`, data) },
  /** TASK-017：删除题目——仅无提交的 draft 作业允许（后端 409 保护） */
  deleteQuestion(assignmentId, questionId) { return client.delete(`/assignments/${assignmentId}/questions/${questionId}`) },
}
