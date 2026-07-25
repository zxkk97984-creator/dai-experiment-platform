import client from './client.js'

/** 统一的实验 API — 仅此入口，不再调用 /notebooks */
export const experimentsAPI = {
  /** 确保学生有 lesson notebook 记录 */
  ensureForLesson(lessonId) {
    return client.post(`/experiments/records/ensure-for-lesson/${lessonId}`)
  },

  /** 确保学生有 module 实验记录 */
  ensureForModule(moduleId) {
    return client.post(`/experiments/records/ensure-for-module/${moduleId}`)
  },

  /** 获取记录详情（含 cells + outputs） */
  getRecordDetail(recordId) {
    return client.get(`/experiments/records/${recordId}`)
  },

  /** 保存 cells 源码（含 record_revision） */
  saveCells(recordId, cells, recordRevision) {
    return client.put(`/experiments/records/${recordId}/cells`, {
      cells,
      record_revision: recordRevision,
    })
  },

  /** 执行 cell */
  executeCell(recordId, cellId, code) {
    return client.post(`/experiments/records/${recordId}/cells/${cellId}/execute`, { code })
  },

  /** 中断 kernel */
  interrupt(recordId) {
    return client.post(`/experiments/records/${recordId}/interrupt`)
  },

  /** 重启 kernel */
  restart(recordId) {
    return client.post(`/experiments/records/${recordId}/restart`)
  },

  // 模块管理
  listModules(params) { return client.get('/experiments/modules', { params }) },
  getModule(id) { return client.get(`/experiments/modules/${id}`) },
  createModule(payload) { return client.post('/experiments/modules', payload) },
  updateModule(id, payload) { return client.patch(`/experiments/modules/${id}`, payload) },
}
