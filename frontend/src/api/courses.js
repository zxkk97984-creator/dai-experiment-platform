import client from './client.js'

export const coursesAPI = {
  list(params) { return client.get('/courses', { params }) },
  create(data) { return client.post('/courses', data) },
  get(id) { return client.get(`/courses/${id}`) },
  update(id, data) { return client.patch(`/courses/${id}`, data) },
  delete(id) { return client.delete(`/courses/${id}`) },
  enroll(courseId) { return client.post(`/courses/${courseId}/enroll`) },
  unenroll(courseId) { return client.delete(`/courses/${courseId}/enroll`) },
  getChapters(courseId) { return client.get(`/courses/${courseId}/chapters`) },
  createChapter(courseId, data) { return client.post(`/courses/${courseId}/chapters`, data) },
  updateChapter(chapterId, data) { return client.patch(`/chapters/${chapterId}`, data) },
  deleteChapter(chapterId) { return client.delete(`/chapters/${chapterId}`) },
  createLesson(chapterId, data) { return client.post(`/chapters/${chapterId}/lessons`, data) },
  updateLesson(lessonId, data) { return client.patch(`/lessons/${lessonId}`, data) },
  deleteLesson(lessonId) { return client.delete(`/lessons/${lessonId}`) },
}
