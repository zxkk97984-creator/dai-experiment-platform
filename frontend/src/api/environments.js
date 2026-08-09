// 环境档位 API（Phase 2：管理员端 + 教师可用环境）
// 管理端点全部仅 admin；available 供教师使用
import client from './client.js'

export const environmentsAPI = {
  // ── 包目录（管理员） ──
  listPackages(status) {
    return client.get('/environments/packages', { params: status ? { status } : {} })
  },
  createPackage(data) {
    return client.post('/environments/packages', data)
  },
  updatePackage(id, data) {
    return client.patch(`/environments/packages/${id}`, data)
  },
  deactivatePackage(id) {
    return client.delete(`/environments/packages/${id}`)
  },

  // ── 环境档位（管理员） ──
  listProfiles() {
    return client.get('/environments/profiles')
  },
  createProfile(data) {
    return client.post('/environments/profiles', data)
  },
  updateProfile(id, data) {
    return client.patch(`/environments/profiles/${id}`, data)
  },
  listVersions(profileId) {
    return client.get(`/environments/profiles/${profileId}/versions`)
  },
  createVersion(profileId, data) {
    return client.post(`/environments/profiles/${profileId}/versions`, data)
  },

  // ── 构建任务（管理员） ──
  createBuild(versionId) {
    return client.post(`/environments/versions/${versionId}/builds`, {})
  },
  listBuilds(limit = 50) {
    return client.get('/environments/builds', { params: { limit } })
  },
  getBuild(jobId) {
    return client.get(`/environments/builds/${jobId}`)
  },
  getBuildLog(jobId) {
    return client.get(`/environments/builds/${jobId}/log`)
  },
  retryBuild(jobId) {
    return client.post(`/environments/builds/${jobId}/retry`)
  },

  // ── 教师可用环境 ──
  listAvailable() {
    return client.get('/environments/available')
  },
}
