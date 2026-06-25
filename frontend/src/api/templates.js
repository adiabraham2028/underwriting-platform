import client from './client'

export const templatesApi = {
  list: () => client.get('/templates'),
  getDefault: () => client.get('/templates/default'),
  upload: (file, name) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', name)
    return client.post('/templates', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  getMapping: (id) => client.get(`/templates/${id}/mapping`),
  updateMapping: (id, data) => client.put(`/templates/${id}/mapping`, data),
  setDefault: (id) => client.post(`/templates/${id}/set-default`),
}
