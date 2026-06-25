import client from './client'

export const knowledgeBaseApi = {
  list: (skip = 0, limit = 50) =>
    client.get('/my/classifications', { params: { skip, limit } }),

  seed: () =>
    client.post('/my/classifications/seed'),

  stats: () =>
    client.get('/my/classifications/stats'),

  delete: (id) =>
    client.delete(`/my/classifications/${id}`),
}
