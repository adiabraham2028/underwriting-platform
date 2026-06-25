import client from './client'

export const aiApi = {
  search: (query) => client.post('/ai/search', { query }),
  chat: (message, dealId, history) => client.post('/ai/chat', { message, deal_id: dealId, history }),
}
