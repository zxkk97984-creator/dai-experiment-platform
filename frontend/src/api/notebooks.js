import client from './client.js'

export const notebooksAPI = {
  /** 获取 notebook 内容和学生副本状态 */
  get(lessonId) {
    return client.get(`/notebooks/${lessonId}`)
  },
  /** 保存学生修改的代码（草稿） */
  saveCells(recordId, cells) {
    return client.put(`/notebooks/records/${recordId}/cells`, { cells })
  },
  /** 执行指定 cell */
  executeCell(recordId, cellId, code) {
    return client.post(`/notebooks/records/${recordId}/cells/${cellId}/execute`, { code })
  },
  /** 中断 kernel */
  interrupt(recordId) {
    return client.post(`/notebooks/records/${recordId}/interrupt`)
  },
  /** 重启 kernel */
  restartKernel(recordId) {
    return client.post(`/notebooks/records/${recordId}/restart-kernel`)
  },
  /** 教师上传 notebook */
  uploadNotebook(lessonId, file) {
    const form = new FormData()
    form.append('file', file)
    return client.post(`/notebooks/lessons/${lessonId}/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}
