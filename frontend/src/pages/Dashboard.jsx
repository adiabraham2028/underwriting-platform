import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { dealsApi } from '../api/deals'
import { templatesApi } from '../api/templates'
import DealCard from '../components/DealCard'
import { Plus, Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

const US_STATES = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']

export default function Dashboard() {
  const [search, setSearch] = useState('')
  const [stateFilter, setStateFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const navigate = useNavigate()

  const { data: deals = [], isLoading, refetch } = useQuery({
    queryKey: ['deals', stateFilter, statusFilter],
    queryFn: () => dealsApi.list({ state: stateFilter || undefined, status: statusFilter || undefined }).then(r => r.data),
  })

  const filteredDeals = deals.filter(d =>
    !search ||
    d.name.toLowerCase().includes(search.toLowerCase()) ||
    d.city.toLowerCase().includes(search.toLowerCase()) ||
    d.address.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search deals..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <select
          value={stateFilter}
          onChange={e => setStateFilter(e.target.value)}
          className="py-2 px-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500"
        >
          <option value="">All States</option>
          {US_STATES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="py-2 px-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500"
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="archived">Archived</option>
          <option value="closed">Closed</option>
        </select>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          New Deal
        </button>
      </div>

      {/* Deal grid */}
      {isLoading ? (
        <div className="text-center py-20 text-gray-500">Loading deals...</div>
      ) : filteredDeals.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          {deals.length === 0
            ? 'No deals yet. Create your first deal!'
            : 'No deals match your filters.'}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredDeals.map(deal => (
            <DealCard key={deal.id} deal={deal} onClick={() => navigate(`/deals/${deal.id}`)} />
          ))}
        </div>
      )}

      {/* Create Deal Modal */}
      {showCreateModal && (
        <CreateDealModal
          onClose={() => setShowCreateModal(false)}
          onCreated={deal => {
            refetch()
            setShowCreateModal(false)
            navigate(`/deals/${deal.id}`)
          }}
        />
      )}
    </div>
  )
}

function CreateDealModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', address: '', city: '', state: 'NY', zip_code: '', total_units: '', template_id: '' })
  const [loading, setLoading] = useState(false)

  const { data: templates = [] } = useQuery({
    queryKey: ['templates'],
    queryFn: () => templatesApi.list().then(r => r.data),
  })

  const handleSubmit = async e => {
    e.preventDefault()
    if (!form.template_id) {
      toast.error('Please select a template')
      return
    }
    setLoading(true)
    try {
      const res = await dealsApi.create({
        ...form,
        total_units: form.total_units ? parseInt(form.total_units) : undefined,
      })
      toast.success('Deal created!')
      onCreated(res.data)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create deal')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h2 className="text-xl font-semibold mb-4">Create New Deal</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Deal Name</label>
            <input type="text" required value={form.name} onChange={e => setForm({...form, name: e.target.value})}
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Address</label>
            <input type="text" required value={form.address} onChange={e => setForm({...form, address: e.target.value})}
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700">City</label>
              <input type="text" required value={form.city} onChange={e => setForm({...form, city: e.target.value})}
                className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">State</label>
              <select value={form.state} onChange={e => setForm({...form, state: e.target.value})}
                className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500">
                {US_STATES.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700">Zip Code</label>
              <input type="text" required value={form.zip_code} onChange={e => setForm({...form, zip_code: e.target.value})}
                className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Total Units</label>
              <input type="number" value={form.total_units} onChange={e => setForm({...form, total_units: e.target.value})}
                className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Underwriting Template <span className="text-red-500">*</span></label>
            <select
              required
              value={form.template_id}
              onChange={e => setForm({...form, template_id: e.target.value})}
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Select a template...</option>
              {templates.map(t => (
                <option key={t.id} value={t.id}>{t.name} v{t.version}{t.is_default ? ' (default)' : ''}</option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={loading || !form.template_id} className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50">
              {loading ? 'Creating...' : 'Create Deal'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
