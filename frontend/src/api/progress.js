import client from './client.js'

/** 学习进度 API（TASK-018）：服务端事实——打开记 in_progress，完成显式操作，可撤回 */
export const progressAPI = {
  /** 打开课时：记录 in_progress 与最后访问时间（幂等，不降级已完成） */
  start(lessonId) { return client.post(`/lessons/${lessonId}/progress/start`) },
  /** 显式完成课时（幂等） */
  complete(lessonId) { return client.post(`/lessons/${lessonId}/progress/complete`) },
  /** 撤回完成：completed → in_progress（幂等） */
  revert(lessonId) { return client.post(`/lessons/${lessonId}/progress/revert`) },
  /** 课程进度聚合：total/completed/percent/next_lesson_id/items */
  getCourse(courseId) { return client.get(`/courses/${courseId}/progress`) },
}
