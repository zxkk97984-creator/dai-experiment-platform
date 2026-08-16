import client from './client.js'

export const dashboardAPI = {
  student() {
    return client.get('/dashboard/student')
  },
  teacher() {
    return client.get('/dashboard/teacher')
  },
  teacherCounts() {
    return client.get('/dashboard/teacher/counts')
  },
}
