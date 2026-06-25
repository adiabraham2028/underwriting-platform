import client from './client'

export const documentsApi = {
  upload: (dealId, file, documentType) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('document_type', documentType)
    return client.post(`/deals/${dealId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list: (dealId) => client.get(`/deals/${dealId}/documents`),
  getStatus: (dealId, docId) => client.get(`/deals/${dealId}/documents/${docId}/status`),
  delete: (dealId, docId) => client.delete(`/deals/${dealId}/documents/${docId}`),
}
