import { useState, useEffect } from 'react'
import client from '../api/client'
import { dealsApi } from '../api/deals'
import FlagsPanel from './FlagsPanel'
import { useQueryClient } from '@tanstack/react-query'

const CATEGORIES = [
  'MarketRent','LTL','Vacancy','Concessions','BadDebt',
  'RUBSInc','RetailInc','OtherInc','Payroll','MgmtFee',
  'Landscaping','Repairs','Turnover','Utilities',
  'SecurityLife','Advert','Admin','Insurance','PropTax',
  'MiscExp','CapEx',
]

const MATCH_COLORS = {
  exact_known:   'bg-green-100 text-green-800',
  exact_gl:      'bg-green-100 text-green-800',
  name_match:    'bg-green-100 text-green-800',
  learned:       'bg-blue-100 text-blue-800',
  ai_high:       'bg-yellow-100 text-yellow-800',
  ai_low:        'bg-red-100 text-red-800',
  human_override:'bg-purple-100 text-purple-800',
}

const INCOME_CATS   = ['MarketRent','LTL','Vacancy','Concessions','BadDebt','RUBSInc','RetailInc','OtherInc']
const OPEX_CATS     = ['Payroll','MgmtFee','Landscaping','Repairs','Turnover','Utilities','SecurityLife','Advert','Admin']
const OTHER_CATS    = ['Insurance','PropTax','MiscExp','CapEx']

function fmt(n)  { return '$' + Math.round(n || 0).toLocaleString() }
function fmtPct(n, d) { return d ? ((n / d) * 100).toFixed(1) + '%' : '—' }

// ── T12 Classifications Tab ────────────────────────────────────────────────

function T12Tab({ items, dealId, onItemChanged }) {
  const handleChange = async (item, newCat) => {
    try {
      await client.patch(
        `/deals/${dealId}/classification-session/items/${item.id}`,
        { final_category: newCat },
      )
      onItemChanged(item.id, newCat)
    } catch (e) {
      console.error('Failed to update category:', e)
    }
  }

  const autoCount = items.filter(i =>
    ['exact_known','exact_gl','name_match'].includes(i.match_type)
  ).length

  return (
    <div>
      <p className="mb-3 text-sm text-gray-500">
        {items.length} line items &bull; {autoCount} auto-classified
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-50 text-left sticky top-0">
              <th className="p-2 border border-gray-200 font-medium">Line Item</th>
              <th className="p-2 border border-gray-200 font-medium">GL Code</th>
              <th className="p-2 border border-gray-200 font-medium">Category</th>
              <th className="p-2 border border-gray-200 font-medium text-right">Annual Total</th>
              <th className="p-2 border border-gray-200 font-medium">Source</th>
            </tr>
          </thead>
          <tbody>
            {items.map(item => (
              <tr key={item.id} className="hover:bg-gray-50 border-b border-gray-100">
                <td className="p-2 border-x border-gray-100">{item.line_item_name}</td>
                <td className="p-2 border-x border-gray-100 font-mono text-xs text-gray-500">
                  {item.account_code || '—'}
                </td>
                <td className="p-2 border-x border-gray-100">
                  <select
                    value={item.final_category || ''}
                    onChange={e => handleChange(item, e.target.value)}
                    className="w-full text-sm rounded border border-gray-200 px-1 py-0.5 bg-white"
                  >
                    {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </td>
                <td className="p-2 border-x border-gray-100 text-right font-mono">
                  {fmt(item.trailing_total)}
                </td>
                <td className="p-2 border-x border-gray-100">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${MATCH_COLORS[item.match_type] || 'bg-gray-100 text-gray-600'}`}>
                    {item.match_type?.replace('_', ' ')}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Key Metrics Tab ────────────────────────────────────────────────────────

function MetricsTab({ items, rrData }) {
  const totals = {}
  items.forEach(item => {
    if (!item.final_category) return
    totals[item.final_category] = (totals[item.final_category] || 0) + (item.trailing_total || 0)
  })

  const totalIncome = INCOME_CATS.reduce((s, c) => s + (totals[c] || 0), 0)
  const totalOpex   = OPEX_CATS.reduce((s, c) => s + (totals[c] || 0), 0)
  const totalOther  = OTHER_CATS.reduce((s, c) => s + (totals[c] || 0), 0)
  const noi         = totalIncome - totalOpex
  const noiAfterAll = noi - totalOther
  const units       = rrData?.total_units || 1

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="font-semibold text-gray-800 mb-3">Income</h3>
          {INCOME_CATS.map(c => totals[c] ? (
            <div key={c} className="flex justify-between py-1 border-b border-gray-100 text-sm">
              <span className="text-gray-600">{c}</span>
              <span className="font-mono">{fmt(totals[c])}</span>
            </div>
          ) : null)}
          <div className="flex justify-between py-2 font-semibold text-sm border-t border-gray-300 mt-1">
            <span>Total Income</span>
            <span className="font-mono">{fmt(totalIncome)}</span>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="font-semibold text-gray-800 mb-3">Operating Expenses</h3>
          {OPEX_CATS.map(c => totals[c] ? (
            <div key={c} className="flex justify-between py-1 border-b border-gray-100 text-sm">
              <span className="text-gray-600">{c}</span>
              <span className="font-mono">{fmt(totals[c])}</span>
            </div>
          ) : null)}
          <div className="flex justify-between py-2 font-semibold text-sm border-t border-gray-300 mt-1">
            <span>Total OpEx</span>
            <span className="font-mono">{fmt(totalOpex)}</span>
          </div>
          <div className="mt-2 space-y-1">
            {OTHER_CATS.map(c => totals[c] ? (
              <div key={c} className="flex justify-between py-0.5 text-sm text-gray-500">
                <span>{c}</span>
                <span className="font-mono">{fmt(totals[c])}</span>
              </div>
            ) : null)}
          </div>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-blue-700">{fmt(noi)}</div>
            <div className="text-xs text-gray-500 mt-1">NOI (before Ins/Tax/CapEx)</div>
          </div>
          <div>
            <div className="text-2xl font-bold">{fmt(noi / units)}</div>
            <div className="text-xs text-gray-500 mt-1">NOI / Unit / Year</div>
          </div>
          <div>
            <div className="text-2xl font-bold">{fmt(noiAfterAll)}</div>
            <div className="text-xs text-gray-500 mt-1">NOI (after All Expenses)</div>
          </div>
          <div>
            <div className="text-2xl font-bold">{fmtPct(totalOpex, totalIncome)}</div>
            <div className="text-xs text-gray-500 mt-1">OpEx Ratio</div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Rent Roll Tab ──────────────────────────────────────────────────────────

function RentRollTab({ rrData }) {
  const [showUnits, setShowUnits] = useState(false)
  if (!rrData) return <p className="text-gray-500 text-sm">No rent roll data. Upload a rent roll document first.</p>

  const { total_units, occupied_units, avg_current_rent, avg_market_rent, occupancy_rate, unit_mix = [] } = rrData

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          ['Total Units',      total_units],
          ['Occupied',         occupied_units],
          ['Vacant',           (total_units || 0) - (occupied_units || 0)],
          ['Occupancy',        occupancy_rate ? (occupancy_rate * 100).toFixed(1) + '%' : '—'],
          ['Avg Current Rent', avg_current_rent ? fmt(avg_current_rent) : '—'],
        ].map(([label, val]) => (
          <div key={label} className="bg-white border border-gray-200 rounded-lg p-3 text-center">
            <div className="text-xl font-bold text-gray-900">{val ?? '—'}</div>
            <div className="text-xs text-gray-500 mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">{unit_mix.length} units parsed</span>
        <button
          onClick={() => setShowUnits(v => !v)}
          className="text-sm text-blue-600 hover:underline"
        >
          {showUnits ? 'Hide' : 'Show'} unit list
        </button>
      </div>

      {showUnits && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-gray-50">
                {['Unit','Type','SF','Status','Current Rent','Market Rent','Lease End'].map(h => (
                  <th key={h} className="p-1.5 border border-gray-200 text-left font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {unit_mix.map((u, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="p-1.5 border-x border-gray-100">{u.unit_number}</td>
                  <td className="p-1.5 border-x border-gray-100 text-gray-500">{u.unit_type}</td>
                  <td className="p-1.5 border-x border-gray-100">{u.sf}</td>
                  <td className="p-1.5 border-x border-gray-100">
                    <span className={`px-1.5 py-0.5 rounded text-xs ${
                      u.status === 'occupied' ? 'bg-green-100 text-green-700' :
                      u.status === 'vacant'   ? 'bg-red-100 text-red-700' :
                      'bg-gray-100 text-gray-600'}`}>
                      {u.status}
                    </span>
                  </td>
                  <td className="p-1.5 border-x border-gray-100 font-mono">{u.base_rent ? fmt(u.base_rent) : '—'}</td>
                  <td className="p-1.5 border-x border-gray-100 font-mono">{u.market_rent ? fmt(u.market_rent) : '—'}</td>
                  <td className="p-1.5 border-x border-gray-100 text-gray-500">{u.lease_expiration || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function ModelReview({ dealId, flags = [], onFlagResolved }) {
  const [activeTab, setActiveTab] = useState('t12')
  const [session, setSession] = useState(null)
  const [items, setItems] = useState([])
  const [rrData, setRrData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [exportingT12, setExportingT12] = useState(false)
  const [exportingRR, setExportingRR] = useState(false)
  const queryClient = useQueryClient()

  useEffect(() => {
    setLoading(true)
    Promise.allSettled([
      client.get(`/deals/${dealId}/classification-session`),
      client.get(`/deals/${dealId}/extractions/rent_roll`),
    ]).then(([sessionRes, rrRes]) => {
      if (sessionRes.status === 'fulfilled') {
        setSession(sessionRes.value.data)
        setItems(sessionRes.value.data?.items || [])
      }
      if (rrRes.status === 'fulfilled') {
        setRrData(rrRes.value.data)
      }
      setLoading(false)
    })
  }, [dealId])

  const handleItemChanged = (itemId, newCat) => {
    setItems(prev => prev.map(i => i.id === itemId ? { ...i, final_category: newCat } : i))
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await client.get(`/deals/${dealId}/model/export`, { responseType: 'blob' })
      const contentDisposition = res.headers['content-disposition'] || ''
      const filenameMatch = contentDisposition.match(/filename="?([^";\n]+)"?/)
      const filename = filenameMatch?.[1] || `model.xlsm`
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('Export failed:', e)
      alert(e.response?.data?.detail || 'Export failed. Check that a template is assigned to this deal.')
    } finally {
      setExporting(false)
    }
  }

  const handleExportT12 = async () => {
    setExportingT12(true)
    try {
      const res = await client.get(`/deals/${dealId}/export/t12`, { responseType: 'blob' })
      const contentDisposition = res.headers['content-disposition'] || ''
      const filenameMatch = contentDisposition.match(/filename="?([^";\n]+)"?/)
      const filename = filenameMatch?.[1] || 'T12.xlsx'
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('T12 export failed:', e)
      alert(e.response?.data?.detail || 'T12 export failed.')
    } finally {
      setExportingT12(false)
    }
  }

  const handleExportRentRoll = async () => {
    setExportingRR(true)
    try {
      const res = await client.get(`/deals/${dealId}/export/rentroll`, { responseType: 'blob' })
      const contentDisposition = res.headers['content-disposition'] || ''
      const filenameMatch = contentDisposition.match(/filename="?([^";\n]+)"?/)
      const filename = filenameMatch?.[1] || 'RentRoll.xlsx'
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('Rent roll export failed:', e)
      alert(e.response?.data?.detail || 'Rent roll export failed.')
    } finally {
      setExportingRR(false)
    }
  }

  const TABS = [
    { id: 't12',      label: 'T12 Classifications' },
    { id: 'rentroll', label: 'Rent Roll' },
    { id: 'metrics',  label: 'Key Metrics' },
    { id: 'flags',    label: `Flags (${flags.filter(f => !f.resolved).length})` },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200 bg-white sticky top-0 z-10">
        <div className="flex gap-1">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleExportT12}
            disabled={exportingT12}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm rounded font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {exportingT12 ? '…' : '↓ T12'}
          </button>
          <button
            onClick={handleExportRentRoll}
            disabled={exportingRR}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm rounded font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {exportingRR ? '…' : '↓ Rent Roll'}
          </button>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="flex items-center gap-2 px-4 py-1.5 bg-green-600 text-white text-sm rounded font-medium hover:bg-green-700 disabled:opacity-50"
          >
            {exporting ? 'Exporting…' : '↓ Export to Excel'}
          </button>
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto p-4">
        {activeTab === 't12' && (
          !session
            ? <p className="text-gray-500 text-sm">No classification data yet. Upload a T12 document first.</p>
            : <T12Tab items={items} dealId={dealId} onItemChanged={handleItemChanged} />
        )}
        {activeTab === 'rentroll' && <RentRollTab rrData={rrData} />}
        {activeTab === 'metrics'  && <MetricsTab items={items} rrData={rrData} />}
        {activeTab === 'flags'    && (
          <FlagsPanel dealId={dealId} flags={flags} onResolved={onFlagResolved} />
        )}
      </div>
    </div>
  )
}
