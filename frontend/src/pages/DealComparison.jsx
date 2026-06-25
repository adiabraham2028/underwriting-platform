import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { dealsApi } from '../api/deals'
import { documentsApi } from '../api/documents'
import client from '../api/client'

const METRICS = [
  { key: 'total_units', label: 'Total Units' },
  { key: 'occupancy_rate', label: 'Occupancy Rate', pct: true },
  { key: 'avg_current_rent', label: 'Avg Current Rent', dollar: true },
  { key: 'avg_market_rent', label: 'Avg Market Rent', dollar: true },
  { key: 'current_noi', label: 'Current NOI', dollar: true },
  { key: 'asking_price', label: 'Asking Price', dollar: true },
  { key: 'cap_rate_in_place', label: 'Cap Rate (In-Place)', pct: true },
  { key: 'price_per_unit', label: 'Price Per Unit', dollar: true },
]

function formatValue(value, metric) {
  if (value == null) return '—'
  if (metric.pct) return `${(value * 100).toFixed(1)}%`
  if (metric.dollar) return `$${Number(value).toLocaleString()}`
  return String(value)
}

async function getDealMetrics(dealId) {
  const res = await client.get(`/deals/${dealId}/model`)
  return res.data
}

export default function DealComparison() {
  const [dealAId, setDealAId] = useState('')
  const [dealBId, setDealBId] = useState('')

  const { data: deals = [] } = useQuery({
    queryKey: ['deals'],
    queryFn: () => dealsApi.list({ limit: 200 }).then(r => r.data),
  })

  const { data: dealA } = useQuery({
    queryKey: ['deal', dealAId],
    queryFn: () => dealsApi.get(dealAId).then(r => r.data),
    enabled: !!dealAId,
  })

  const { data: dealB } = useQuery({
    queryKey: ['deal', dealBId],
    queryFn: () => dealsApi.get(dealBId).then(r => r.data),
    enabled: !!dealBId,
  })

  const { data: extraA = [] } = useQuery({
    queryKey: ['extractions', dealAId],
    queryFn: async () => {
      const res = await client.get(`/deals/${dealAId}/documents`)
      return res.data
    },
    enabled: !!dealAId,
  })

  const { data: extraB = [] } = useQuery({
    queryKey: ['extractions', dealBId],
    queryFn: async () => {
      const res = await client.get(`/deals/${dealBId}/documents`)
      return res.data
    },
    enabled: !!dealBId,
  })

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Deal Comparison</h1>

      <div className="grid grid-cols-2 gap-6 mb-8">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Deal A</label>
          <select
            value={dealAId}
            onChange={e => setDealAId(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Select a deal...</option>
            {deals.map(d => <option key={d.id} value={d.id}>{d.name} — {d.city}, {d.state}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Deal B</label>
          <select
            value={dealBId}
            onChange={e => setDealBId(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Select a deal...</option>
            {deals.map(d => <option key={d.id} value={d.id}>{d.name} — {d.city}, {d.state}</option>)}
          </select>
        </div>
      </div>

      {dealAId && dealBId && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-6 py-3 font-medium text-gray-700">Metric</th>
                <th className="text-right px-6 py-3 font-medium text-gray-700">{dealA?.name || 'Deal A'}</th>
                <th className="text-right px-6 py-3 font-medium text-gray-700">{dealB?.name || 'Deal B'}</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-100 bg-gray-50">
                <td colSpan={3} className="px-6 py-2 font-semibold text-gray-700 text-xs uppercase tracking-wide">Property</td>
              </tr>
              <tr className="border-b border-gray-100">
                <td className="px-6 py-3 text-gray-600">Address</td>
                <td className="px-6 py-3 text-right text-gray-900">{dealA ? `${dealA.city}, ${dealA.state}` : '—'}</td>
                <td className="px-6 py-3 text-right text-gray-900">{dealB ? `${dealB.city}, ${dealB.state}` : '—'}</td>
              </tr>
              <tr className="border-b border-gray-100">
                <td className="px-6 py-3 text-gray-600">Status</td>
                <td className="px-6 py-3 text-right text-gray-900">{dealA?.status || '—'}</td>
                <td className="px-6 py-3 text-right text-gray-900">{dealB?.status || '—'}</td>
              </tr>
              <tr className="border-b border-gray-100">
                <td className="px-6 py-3 text-gray-600">Total Units</td>
                <td className="px-6 py-3 text-right text-gray-900">{dealA?.total_units || '—'}</td>
                <td className="px-6 py-3 text-right text-gray-900">{dealB?.total_units || '—'}</td>
              </tr>
              <tr className="border-b border-gray-100 bg-gray-50">
                <td colSpan={3} className="px-6 py-2 font-semibold text-gray-700 text-xs uppercase tracking-wide">Flags</td>
              </tr>
              <tr className="border-b border-gray-100">
                <td className="px-6 py-3 text-gray-600">Unresolved Flags</td>
                <td className="px-6 py-3 text-right text-gray-900">{dealA?.flag_count ?? '—'}</td>
                <td className="px-6 py-3 text-right text-gray-900">{dealB?.flag_count ?? '—'}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {!dealAId || !dealBId ? (
        <div className="text-center py-16 text-gray-400">Select two deals above to compare them side by side.</div>
      ) : null}
    </div>
  )
}
