import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { classificationApi } from '../api/classification'
import ClassificationBadge from '../components/ClassificationBadge'
import { ArrowLeft, ChevronDown, ChevronRight, CheckCircle2, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'

const THE_21_CATEGORIES = [
  'MarketRent', 'LTL', 'Vacancy', 'Concessions', 'BadDebt',
  'RUBSInc', 'RetailInc', 'OtherInc',
  'Payroll', 'MgmtFee', 'Landscaping', 'Repairs', 'Turnover',
  'Utilities', 'SecurityLife', 'Advert', 'Admin',
  'Insurance', 'PropTax', 'MiscExp', 'CapEx',
]

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function fmt(n) {
  if (n == null) return '-'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)
}

function MatchTypePill({ type }) {
  const styles = {
    exact_known: 'bg-blue-100 text-blue-700',
    ai_high: 'bg-green-100 text-green-700',
    ai_low: 'bg-orange-100 text-orange-700',
    human_override: 'bg-purple-100 text-purple-700',
  }
  const labels = {
    exact_known: 'Exact Match',
    ai_high: 'AI High',
    ai_low: 'AI Low',
    human_override: 'Human',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[type] || 'bg-gray-100 text-gray-600'}`}>
      {labels[type] || type}
    </span>
  )
}

function ItemRow({ item, sessionId, dealId, onUpdated }) {
  const [expanded, setExpanded] = useState(false)
  const [localCategory, setLocalCategory] = useState(item.final_category)

  const mutation = useMutation({
    mutationFn: (category) =>
      classificationApi.updateItem(dealId, sessionId, item.id, { final_category: category }),
    onSuccess: () => {
      toast.success('Category updated')
      onUpdated()
    },
    onError: () => toast.error('Failed to update category'),
  })

  const handleCategoryChange = (e) => {
    const cat = e.target.value
    setLocalCategory(cat)
    mutation.mutate(cat)
  }

  return (
    <>
      <tr className={`border-b border-gray-100 hover:bg-gray-50 ${item.was_corrected ? 'bg-purple-50' : ''}`}>
        <td className="px-4 py-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-left text-sm font-medium text-gray-900"
          >
            {expanded ? <ChevronDown className="h-3.5 w-3.5 text-gray-400" /> : <ChevronRight className="h-3.5 w-3.5 text-gray-400" />}
            {item.line_item_name}
          </button>
        </td>
        <td className="px-4 py-3 text-xs text-gray-500 font-mono">{item.account_code || '-'}</td>
        <td className="px-4 py-3 text-sm text-gray-700 text-right">{fmt(item.trailing_total)}</td>
        <td className="px-4 py-3">
          <select
            value={localCategory}
            onChange={handleCategoryChange}
            disabled={mutation.isPending}
            className="text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white disabled:opacity-50"
          >
            {THE_21_CATEGORIES.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </td>
        <td className="px-4 py-3">
          <ClassificationBadge confidence={item.ai_confidence} matchType={item.match_type} />
        </td>
        <td className="px-4 py-3">
          <MatchTypePill type={item.match_type} />
        </td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50 border-b border-gray-100">
          <td colSpan={6} className="px-8 py-3">
            <div className="text-xs text-gray-600">
              <p className="font-medium mb-2">Monthly Values</p>
              <div className="grid grid-cols-6 gap-2">
                {MONTH_LABELS.map(month => (
                  <div key={month} className="text-center">
                    <div className="text-gray-400">{month}</div>
                    <div className="font-medium">{fmt(item.monthly_values?.[month])}</div>
                  </div>
                ))}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function ClassificationReview() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState('all')

  const { data: sessionData, isLoading, error } = useQuery({
    queryKey: ['classification-session', id],
    queryFn: () => classificationApi.getSession(id).then(r => r.data),
    retry: false,
  })

  const approveMutation = useMutation({
    mutationFn: () => classificationApi.approveSession(id, sessionData.id),
    onSuccess: () => {
      toast.success('Classifications applied to model')
      queryClient.invalidateQueries(['classification-session', id])
      navigate(`/deals/${id}`)
    },
    onError: () => toast.error('Failed to apply classifications'),
  })

  const bulkApproveMutation = useMutation({
    mutationFn: () => classificationApi.bulkApprove(id, sessionData.id),
    onSuccess: (res) => {
      toast.success(`Accepted ${res.data.accepted_count} high-confidence items`)
      queryClient.invalidateQueries(['classification-session', id])
    },
    onError: () => toast.error('Bulk accept failed'),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (error || !sessionData) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center gap-3 mb-4">
          <button onClick={() => navigate(`/deals/${id}`)} className="p-1.5 hover:bg-gray-100 rounded-md">
            <ArrowLeft className="h-5 w-5 text-gray-600" />
          </button>
          <h1 className="text-xl font-bold text-gray-900">T12 Classifications</h1>
        </div>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
          <AlertCircle className="h-8 w-8 text-yellow-500 mx-auto mb-2" />
          <p className="text-yellow-800 font-medium">No classification session found for this deal.</p>
          <p className="text-yellow-600 text-sm mt-1">Upload and process a T12 document first.</p>
        </div>
      </div>
    )
  }

  const items = sessionData.items || []
  const filteredItems = filter === 'all' ? items
    : filter === 'review' ? items.filter(i => i.match_type === 'ai_low')
    : items.filter(i => i.match_type !== 'ai_low')

  const total = items.length
  const autoAccepted = sessionData.auto_accepted
  const needsReview = sessionData.needs_review
  const progress = total > 0 ? Math.round((autoAccepted / total) * 100) : 0
  const isApplied = sessionData.status === 'applied'

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate(`/deals/${id}`)} className="p-1.5 hover:bg-gray-100 rounded-md">
          <ArrowLeft className="h-5 w-5 text-gray-600" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900">Review T12 Classifications</h1>
          <p className="text-sm text-gray-500">
            Session created {new Date(sessionData.created_at).toLocaleString()}
            {isApplied && <span className="ml-2 text-green-600 font-medium">Applied</span>}
          </p>
        </div>
        <div className="flex gap-3">
          {!isApplied && needsReview > 0 && (
            <button
              onClick={() => bulkApproveMutation.mutate()}
              disabled={bulkApproveMutation.isPending}
              className="px-4 py-2 text-sm border border-blue-300 text-blue-700 rounded-md hover:bg-blue-50 disabled:opacity-50"
            >
              Accept All High-Confidence
            </button>
          )}
          {!isApplied && (
            <button
              onClick={() => approveMutation.mutate()}
              disabled={approveMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              <CheckCircle2 className="h-4 w-4" />
              {approveMutation.isPending ? 'Applying...' : 'Apply to Model'}
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">
            {autoAccepted} of {total} items auto-classified
            {needsReview > 0 && <span className="ml-2 text-orange-600">{needsReview} need review</span>}
          </span>
          <span className="text-sm text-gray-500">{progress}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 rounded-full h-2 transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex gap-4 mt-2 text-xs text-gray-500">
          <span><span className="inline-block w-2 h-2 bg-blue-100 border border-blue-400 rounded-sm mr-1"></span>Known Match: {items.filter(i => i.match_type === 'exact_known').length}</span>
          <span><span className="inline-block w-2 h-2 bg-green-100 border border-green-400 rounded-sm mr-1"></span>AI High: {items.filter(i => i.match_type === 'ai_high').length}</span>
          <span><span className="inline-block w-2 h-2 bg-orange-100 border border-orange-400 rounded-sm mr-1"></span>AI Low: {items.filter(i => i.match_type === 'ai_low').length}</span>
          <span><span className="inline-block w-2 h-2 bg-purple-100 border border-purple-400 rounded-sm mr-1"></span>Human: {items.filter(i => i.was_corrected).length}</span>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {[
          { id: 'all', label: `All (${items.length})` },
          { id: 'review', label: `Needs Review (${items.filter(i => i.match_type === 'ai_low').length})` },
          { id: 'accepted', label: `Auto-Accepted (${items.filter(i => i.match_type !== 'ai_low').length})` },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setFilter(tab.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              filter === tab.id
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-3 font-medium text-gray-700">Line Item</th>
              <th className="text-left px-4 py-3 font-medium text-gray-700">Account Code</th>
              <th className="text-right px-4 py-3 font-medium text-gray-700">Trailing Total</th>
              <th className="text-left px-4 py-3 font-medium text-gray-700">Category</th>
              <th className="text-left px-4 py-3 font-medium text-gray-700">Confidence</th>
              <th className="text-left px-4 py-3 font-medium text-gray-700">Match Type</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map(item => (
              <ItemRow
                key={item.id}
                item={item}
                sessionId={sessionData.id}
                dealId={id}
                onUpdated={() => queryClient.invalidateQueries(['classification-session', id])}
              />
            ))}
            {filteredItems.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">No items to show.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
