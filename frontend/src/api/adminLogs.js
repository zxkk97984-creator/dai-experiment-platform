import client from './client.js'

export const adminLogsAPI = {
  /** 查询日志：source=api|worker，可按 level / 关键词过滤 */
  listLogs(params) { return client.get('/admin/logs', { params }) },
  /** 可用日志文件列表（含轮转副本） */
  listFiles() { return client.get('/admin/logs/files') },
}
