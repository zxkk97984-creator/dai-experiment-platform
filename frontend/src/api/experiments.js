import client from './client.js'

export const experimentsAPI = {
  // 模块
  listModules(params) { return client.get('/experiments/modules', { params }) },
  createModule(data) { return client.post('/experiments/modules', data) },
  getModule(id) { return client.get(`/experiments/modules/${id}`) },

  // 记录
  createRecord(data) { return client.post('/experiments/records', data) },
  listRecords(params) { return client.get('/experiments/records', { params }) },
  /** 确保学生有实验记录（不存在则创建） */
  ensureRecord(moduleId) { return client.post(`/experiments/records/ensure/${moduleId}`) },
  /** 获取实验记录详情（含 cells + outputs） */
  getRecordDetail(recordId) { return client.get(`/experiments/records/${recordId}`) },

  // Cells 操作
  /** 保存 cells 源码 */
  saveCells(recordId, cells, cellOrder) {
    return client.put(`/experiments/records/${recordId}/cells`, { cells, cell_order: cellOrder })
  },
  /** 执行代码 */
  executeCell(recordId, cellId, code) {
    return client.post(`/experiments/records/${recordId}/cells/${cellId}/execute`, { code })
  },
  /** 中断执行 */
  interrupt(recordId) { return client.post(`/experiments/records/${recordId}/interrupt`) },
  /** 重启 kernel */
  restartKernel(recordId) { return client.post(`/experiments/records/${recordId}/restart`) },
}
