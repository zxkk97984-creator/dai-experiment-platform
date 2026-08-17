import client from './client.js'

export const examsAPI = {
  list(params) { return client.get('/exams', { params }) },
  create(data) { return client.post('/exams', data) },
  get(id) { return client.get(`/exams/${id}`) },
  update(id, data) { return client.patch(`/exams/${id}`, data) },
  delete(id) { return client.delete(`/exams/${id}`) },
  getSession(id) { return client.get(`/exams/${id}/session`) },
  importAudienceStudents(examId, kind, file) {
    const formData = new FormData()
    formData.append('file', file)
    return client.post(`/exams/${examId}/audience/import`, formData, { params: { kind } })
  },
  start(id) { return client.post(`/exams/${id}/start`) },
  submit(id, data = {}) { return client.post(`/exams/${id}/submit`, data) },
  getGrades(id) { return client.get(`/exams/${id}/grades`) },
  getGradeDetail(examId, submissionId) { return client.get(`/exams/${examId}/grades/${submissionId}`) },
  updateGradeAnswerScore(examId, submissionId, answerId, score, reason) {
    return client.patch(`/exams/${examId}/grades/${submissionId}/answers/${answerId}/score`, { score, reason })
  },
  updateGradeQuestionScore(examId, submissionId, questionId, score, reason) {
    return client.patch(`/exams/${examId}/grades/${submissionId}/questions/${questionId}/score`, { score, reason })
  },
  getQuestions(id) { return client.get(`/exams/${id}/questions`) },
  createQuestion(id, data) { return client.post(`/exams/${id}/questions`, data) },
  updateQuestion(examId, qId, data) { return client.patch(`/exams/${examId}/questions/${qId}`, data) },
  deleteQuestion(examId, qId) { return client.delete(`/exams/${examId}/questions/${qId}`) },
  saveAnswer(examId, qId, data) { return client.put(`/exams/${examId}/answers/${qId}`, data) },
  saveAnswers(examId, answers) { return client.put(`/exams/${examId}/answers`, { answers }) },
  sampleRun(examId, questionId, data) { return client.post(`/exams/${examId}/questions/${questionId}/sample-run`, data) },
  getMyGrade(id) { return client.get(`/exams/${id}/my-grade`) },
  releaseReview(id) { return client.post(`/exams/${id}/review-release`) },
  extendSubmission(examId, submissionId, minutes) {
    return client.patch(`/exams/${examId}/submissions/${submissionId}/extend`, { minutes })
  },
  forceSubmit(examId, submissionId) {
    return client.post(`/exams/${examId}/submissions/${submissionId}/force-submit`)
  },
}
