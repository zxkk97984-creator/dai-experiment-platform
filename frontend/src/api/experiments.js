import client from './client.js'

export const experimentsAPI = {
  listModules(params) { return client.get('/experiments/modules', { params }) },
  createModule(data) { return client.post('/experiments/modules', data) },
  getModule(id) { return client.get(`/experiments/modules/${id}`) },
  createRecord(data) { return client.post('/experiments/records', data) },
  listRecords(params) { return client.get('/experiments/records', { params }) },
}
