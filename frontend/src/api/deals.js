import client from './client'

export const dealsApi = {
  list: (params) => client.get('/deals', { params }),
  get: (id) => client.get(`/deals/${id}`),
  create: (data) => client.post('/deals', data),
  update: (id, data) => client.patch(`/deals/${id}`, data),
  delete: (id) => client.delete(`/deals/${id}`),
  getFlags: (id, params) => client.get(`/deals/${id}/flags`, { params }),
  resolveFlag: (dealId, flagId) => client.patch(`/deals/${dealId}/flags/${flagId}`),
  getSnapshots: (id) => client.get(`/deals/${id}/snapshots`),
  migrateTemplate: (id) => client.post(`/deals/${id}/migrate-template`),
  getModel: (id, snapshotId) => client.get(`/deals/${id}/model`, { params: snapshotId ? { snapshot_id: snapshotId } : {} }),
  saveModel: (id, data) => client.put(`/deals/${id}/model`, data),
  exportModel: (id) => client.get(`/deals/${id}/model/export`, { responseType: 'blob' }),
  diffSnapshots: (id, a, b) => client.get(`/deals/${id}/model/diff`, { params: { snapshot_a: a, snapshot_b: b } }),
}
