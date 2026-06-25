import client from './client'

export const classificationApi = {
  getSession: (dealId) =>
    client.get(`/deals/${dealId}/classification-session`),

  updateItem: (dealId, sessionId, itemId, data) =>
    client.post(`/deals/${dealId}/classification-session/${sessionId}/items/${itemId}`, data),

  approveSession: (dealId, sessionId) =>
    client.post(`/deals/${dealId}/classification-session/${sessionId}/approve`),

  bulkApprove: (dealId, sessionId) =>
    client.post(`/deals/${dealId}/classification-session/${sessionId}/bulk-approve`),
}
