import client from './client.js'

export const studioAPI = {
  // 模板管理
  listTemplates(params) { return client.get('/studio/templates', { params }) },
  getTemplate(id) { return client.get(`/studio/templates/${id}`) },
  createTemplate(data) { return client.post('/studio/templates', data) },
  updateTemplate(id, data) { return client.patch(`/studio/templates/${id}`, data) },
  bindTemplate(id, data) { return client.post(`/studio/templates/${id}/bind`, data) },

  // 草稿
  saveDraft(id, data) { return client.put(`/studio/templates/${id}/draft`, data) },

  // 导入
  importNew(formData) {
    return client.post('/studio/templates/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })
  },
  importExisting(id, formData) {
    return client.post(`/studio/templates/${id}/import`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })
  },

  // 发布与版本
  publish(id) { return client.post(`/studio/templates/${id}/publish`) },
  getVersions(id) { return client.get(`/studio/templates/${id}/versions`) },
  getVersion(id, versionId) { return client.get(`/studio/templates/${id}/versions/${versionId}`) },

  // 导出
  exportDraft(id) {
    return client.get(`/studio/templates/${id}/export?scope=draft`, { responseType: 'blob' })
  },
  exportVersion(id, versionId) {
    return client.get(`/studio/templates/${id}/export?version_id=${versionId}`, { responseType: 'blob' })
  },

  // 预览
  previewRun(id, data) { return client.post(`/studio/templates/${id}/preview/run`, data) },
  previewInterrupt(id) { return client.post(`/studio/templates/${id}/preview/interrupt`) },
  previewReset(id) { return client.post(`/studio/templates/${id}/preview/reset`) },
}
