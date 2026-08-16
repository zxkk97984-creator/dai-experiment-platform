import client from './client.js'

export const statisticsAPI = {
  teacherGrades() {
    return client.get('/teacher/grade-statistics')
  },
}
