import client from './client'

export const expenseCompsApi = {
  import: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return client.post('/my/expense-comps/import', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  list: () =>
    client.get('/my/expense-comps'),

  delete: (id) =>
    client.delete(`/my/expense-comps/${id}`),

  getIncExpVar: (dealId) =>
    client.get(`/deals/${dealId}/inc-exp-var`),

  getComparison: (dealId, compIds = []) => {
    const params = compIds.length ? `?comp_ids=${compIds.join(',')}` : ''
    return client.get(`/deals/${dealId}/comparison${params}`)
  },
}
