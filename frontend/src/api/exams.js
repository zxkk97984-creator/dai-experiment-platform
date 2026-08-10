import client from './client.js'

export const examsAPI = {
  list(params) { return client.get('/exams', { params }) },
    create(data) { return client.post('/exams', data) },
    get(id) { return client.get(`/exams/${id}`) },
    update(id, data) { return client.patch(`/exams/${id}`, data) },
    delete(id) { return client.delete(`/exams/${id}`) },
    start(id) { return client.post(`/exams/${id}/start`) },
    submit(id, data) { return client.post(`/exams/${id}/submit`, data) },
    getGrades(id) { return client.get(`/exams/${id}/grades`) },
    getGradeDetail(examId, submissionId) { return client.get(`/exams/${examId}/grades/${submissionId}`) },
    getQuestions(id) { return client.get(`/exams/${id}/questions`) },
    createQuestion(id, data) { return client.post(`/exams/${id}/questions`, data) },
    updateQuestion(examId, qId, data) { return client.patch(`/exams/${examId}/questions/${qId}`, data) },
    deleteQuestion(examId, qId) { return client.delete(`/exams/${examId}/questions/${qId}`) },
    saveAnswer(examId, qId, data) { return client.put(`/exams/${examId}/answers/${qId}`, data) },
    getMyGrade(id) { return client.get(`/exams/${id}/my-grade`) },
}
