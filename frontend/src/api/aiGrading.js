/** AI 评分 API——题目配置、Rubric 管理、教师复核 */
import client from './client'

export const aiGradingAPI = {
  /** 获取题目 AI 评分配置 */
  getConfig(kind, id) {
    return client.get(`/ai-grading/questions/${kind}/${id}/config`)
  },

  /** 更新题目 AI 评分配置 */
  updateConfig(kind, id, data) {
    return client.put(`/ai-grading/questions/${kind}/${id}/config`, data)
  },

  /** 列出题目 Rubric 版本 */
  listRubrics(kind, id) {
    return client.get(`/ai-grading/questions/${kind}/${id}/rubrics`)
  },

  /** 生成新 Rubric */
  generateRubric(kind, id) {
    return client.post(`/ai-grading/questions/${kind}/${id}/rubrics/generate`)
  },

  /** 修改 draft Rubric */
  updateRubric(id, data) {
    return client.patch(`/ai-grading/rubrics/${id}`, data)
  },

  /** 锁定 Rubric */
  lockRubric(id) {
    return client.post(`/ai-grading/rubrics/${id}/lock`)
  },

  /** 获取评分列表（教师复核） */
  listGrades(params) {
    return client.get('/ai-grading/grades', { params })
  },

  /** 获取评分详情 */
  getGrade(id) {
    return client.get(`/ai-grading/grades/${id}`)
  },

  /** 重试 AI 评分 */
  retryGrade(id) {
    return client.post(`/ai-grading/grades/${id}/retry`)
  },

  /** 覆盖评分 */
  overrideGrade(id, data) {
    return client.post(`/ai-grading/grades/${id}/override`, data)
  },

  /** 统一重评 */
  regradeQuestion(kind, questionId) {
    return client.post(`/ai-grading/questions/${kind}/${questionId}/regrade`)
  },
}
