import client from './client.js'

export const submissionsAPI = {
  unified(params) {
    return client.get('/submissions/unified', { params })
  },
  getTeacherJudgeDetail(id) {
    return client.get(`/judge/submissions/${id}/teacher`)
  },
}
