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
  listWhitelist(courseId, params) { return client.get(`/courses/${courseId}/whitelist`, { params }) },
  addWhitelistStudent(courseId, studentId) { return client.post(`/courses/${courseId}/whitelist`, { student_id: studentId }) },
  removeWhitelistStudent(courseId, studentId) { return client.delete(`/courses/${courseId}/whitelist/${studentId}`) },
  // ── 教师上传视频 ──
  uploadLessonVideo(lessonId, file, { onUploadProgress, signal } = {}) {
    const formData = new FormData()
    formData.append('file', file)
    return client.put(`/lessons/${lessonId}/video-file`, formData, {
      // multipart 覆盖实例 JSON Content-Type，由 Axios/浏览器生成 boundary
      headers: { 'Content-Type': undefined },
      // 上传单独放宽超时（600 秒），不修改普通 API 的 30 秒默认值
      timeout: 600000,
      onUploadProgress,
      signal,
    })
  },
  deleteLessonVideo(lessonId) { return client.delete(`/lessons/${lessonId}/video-file`) },
  getLessonVideoPlaybackUrl(lessonId) { return client.get(`/lessons/${lessonId}/video-playback-url`) },
  // ── 课程封面 ──
  uploadCourseCover(courseId, file, { onUploadProgress, signal } = {}) {
    const formData = new FormData()
    formData.append('file', file)
    return client.put(`/courses/${courseId}/cover`, formData, {
      // multipart 覆盖实例 JSON Content-Type，由 Axios/浏览器生成 boundary
      headers: { 'Content-Type': undefined },
      // 上传单独放宽超时（600 秒），不修改普通 API 的 30 秒默认值
      timeout: 600000,
      onUploadProgress,
      signal,
    })
  },
  deleteCourseCover(courseId) { return client.delete(`/courses/${courseId}/cover`) },
}
