import client from './client.js'

export const jupyterAPI = {
  getEntry() { return client.get('/jupyter/entry') },
  getTemplates() { return client.get('/jupyter/templates') },
  copyTemplate(templateId) { return client.post(`/jupyter/templates/${templateId}/copy`) },
}
