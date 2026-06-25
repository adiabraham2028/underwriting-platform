import { useState } from 'react'
import { dealsApi } from '../api/deals'
import { Flag, AlertTriangle, Info, CheckCircle, Filter } from 'lucide-react'
import toast from 'react-hot-toast'

const SEVERITY_CONFIG = {
  critical: { color: 'text-red-600 bg-red-50 border-red-200', icon: AlertTriangle, label: 'Critical' },
  warning: { color: 'text-amber-600 bg-amber-50 border-amber-200', icon: Flag, label: 'Warning' },
  info: { color: 'text-blue-600 bg-blue-50 border-blue-200', icon: Info, label: 'Info' },
}

export default function FlagsPanel({ dealId, flags = [], onResolved, compact = false }) {
  const [showResolved, setShowResolved] = useState(false)
  const [severityFilter, setSeverityFilter] = useState('')

  const handleResolve = async (flagId) => {
    try {
      await dealsApi.resolveFlag(dealId, flagId)
      toast.success('Flag resolved')
      onResolved?.()
    } catch {
      toast.error('Failed to resolve flag')
    }
  }

  const filtered = flags.filter(f => {
    if (!showResolved && f.resolved) return false
    if (severityFilter && f.severity !== severityFilter) return false
    return true
  })

  const grouped = {
    critical: filtered.filter(f => f.severity === 'critical' && !f.resolved),
    warning: filtered.filter(f => f.severity === 'warning' && !f.resolved),
    info: filtered.filter(f => f.severity === 'info' && !f.resolved),
    resolved: filtered.filter(f => f.resolved),
  }

  const unresolvedCount = flags.filter(f => !f.resolved).length

  return (
    <div className={compact ? '' : 'max-w-2xl'}>
      {!compact && (
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Flags <span className="text-sm font-normal text-gray-500">({unresolvedCount} unresolved)</span>
          </h2>
        </div>
      )}
      {compact && (
        <div className="p-3 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-900">
            Flags <span className="text-gray-500 font-normal">({unresolvedCount})</span>
          </h3>
        </div>
      )}

      <div className={`flex items-center gap-2 ${compact ? 'px-3 py-2 border-b border-gray-100' : 'mb-4'}`}>
        <button
          onClick={() => setShowResolved(!showResolved)}
          className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${showResolved ? 'bg-gray-200 text-gray-800' : 'bg-white border border-gray-300 text-gray-600'}`}
        >
          <CheckCircle className="h-3 w-3" />
          {showResolved ? 'Hide Resolved' : 'Show Resolved'}
        </button>
        <select
          value={severityFilter}
          onChange={e => setSeverityFilter(e.target.value)}
          className="px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none"
        >
          <option value="">All Severities</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
        </select>
      </div>

      <div className={compact ? 'p-3 space-y-2' : 'space-y-3'}>
        {['critical', 'warning', 'info'].map(severity => {
          const group = grouped[severity]
          if (group.length === 0) return null
          const cfg = SEVERITY_CONFIG[severity]
          const Icon = cfg.icon
          return (
            <div key={severity}>
              <p className={`text-xs font-semibold uppercase tracking-wide mb-1.5 ${severity === 'critical' ? 'text-red-700' : severity === 'warning' ? 'text-amber-700' : 'text-blue-700'}`}>
                {cfg.label} ({group.length})
              </p>
              {group.map(flag => (
                <div key={flag.id} className={`border rounded-lg p-3 mb-2 ${cfg.color}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-start gap-2 flex-1 min-w-0">
                      <Icon className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
                      <div className="min-w-0">
                        <p className="text-xs font-semibold">{flag.field_name} <span className="font-normal text-gray-500">({flag.cell_address})</span></p>
                        <p className="text-xs mt-0.5">{flag.description}</p>
                        {flag.source_a_value && (
                          <p className="text-xs mt-1 text-gray-600">
                            {flag.source_a_label}: {flag.source_a_value} vs {flag.source_b_label}: {flag.source_b_value}
                          </p>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => handleResolve(flag.id)}
                      className="flex-shrink-0 text-xs font-medium underline hover:no-underline"
                    >
                      Resolve
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )
        })}

        {showResolved && grouped.resolved.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1.5">Resolved ({grouped.resolved.length})</p>
            {grouped.resolved.map(flag => (
              <div key={flag.id} className="border border-gray-200 bg-gray-50 rounded-lg p-3 mb-2">
                <p className="text-xs text-gray-500 line-through">{flag.field_name}: {flag.description}</p>
              </div>
            ))}
          </div>
        )}

        {filtered.length === 0 && (
          <div className="text-center py-6 text-gray-400 text-sm">
            No flags to show.
          </div>
        )}
      </div>
    </div>
  )
}
