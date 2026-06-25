import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { expenseCompsApi } from '../api/expense_comps'
import { ArrowLeft, X, Search } from 'lucide-react'

// ---------------------------------------------------------------------------
// Row definitions — the canonical display structure
// ---------------------------------------------------------------------------

const R = (type, label, key, opts = {}) => ({ type, label, key, ...opts })

const ROW_DEFS = [
  R('section',  'INCOME'),
  R('data',     'Market Rent',           'MarketRent',        { isIncome: true }),
  R('data',     'Loss to Lease',         'LTL',               { isIncome: true }),
  R('computed', 'Base Scheduled Rent',   'BaseScheduledRent', { isIncome: true,
      compute: m => (m.MarketRent || 0) + (m.LTL || 0) }),
  R('data',     'Vacancy',               'Vacancy',           { isIncome: true }),
  R('data',     'Concessions',           'Concessions',       { isIncome: true }),
  R('data',     'Bad Debt',              'BadDebt',           { isIncome: true }),
  R('subtotal', 'Rental Income',         'RentalIncome',      { isIncome: true,
      compute: m => (m.MarketRent||0)+(m.LTL||0)+(m.Vacancy||0)+(m.Concessions||0)+(m.BadDebt||0) }),
  R('data',     'RUBS Income',           'RUBSInc',           { isIncome: true }),
  R('data',     'Retail Income',         'RetailInc',         { isIncome: true }),
  R('data',     'Other Income',          'OtherInc',          { isIncome: true }),
  R('subtotal', 'Total Income',          'TotalIncome',       { isIncome: true,
      compute: m => {
        const rental = (m.MarketRent||0)+(m.LTL||0)+(m.Vacancy||0)+(m.Concessions||0)+(m.BadDebt||0)
        return rental + (m.RUBSInc||0) + (m.RetailInc||0) + (m.OtherInc||0)
      }}),
  R('pct',      'Vacancy %',             'VacancyPct',
      { compute: m => m.MarketRent ? Math.abs(m.Vacancy||0) / m.MarketRent : null }),
  R('pct',      'Economic Vacancy %',    'EconVacancyPct',
      { compute: m => {
        if (!m.MarketRent) return null
        const rental = (m.MarketRent||0)+(m.LTL||0)+(m.Vacancy||0)+(m.Concessions||0)+(m.BadDebt||0)
        return (m.MarketRent - rental) / m.MarketRent
      }}),

  R('section',  'OPERATING EXPENSES'),
  R('data',     'Payroll',                    'Payroll'),
  R('data',     'Management Fee',             'MgmtFee'),
  R('data',     'Landscaping',                'Landscaping'),
  R('data',     'Repairs and Maintenance',    'Repairs'),
  R('data',     'Maintenance Turnover',       'Turnover'),
  R('data',     'Utilities',                  'Utilities'),
  R('data',     'Security and Life Safety',   'SecurityLife'),
  R('data',     'Advertising & Promotion',    'Advert'),
  R('data',     'Admin / Other Expenses',     'Admin'),
  R('subtotal', 'Total Operating Expenses',   'TotalOpEx',
      { compute: m => (m.Payroll||0)+(m.MgmtFee||0)+(m.Landscaping||0)+(m.Repairs||0)+
                      (m.Turnover||0)+(m.Utilities||0)+(m.SecurityLife||0)+(m.Advert||0)+(m.Admin||0) }),

  R('section',  'OTHER EXPENSES'),
  R('data',     'Insurance',             'Insurance'),
  R('data',     'Property Taxes',        'PropTax'),
  R('data',     'Misc. Expense',         'MiscExp'),
  R('data',     'Capital Replacement',   'CapEx'),
  R('subtotal', 'Total Other Expenses',  'TotalOtherEx',
      { compute: m => (m.Insurance||0)+(m.PropTax||0)+(m.MiscExp||0)+(m.CapEx||0) }),

  R('total',    'Total Expenses',        'TotalEx',
      { compute: m => {
        const opEx = (m.Payroll||0)+(m.MgmtFee||0)+(m.Landscaping||0)+(m.Repairs||0)+
                     (m.Turnover||0)+(m.Utilities||0)+(m.SecurityLife||0)+(m.Advert||0)+(m.Admin||0)
        const otherEx = (m.Insurance||0)+(m.PropTax||0)+(m.MiscExp||0)+(m.CapEx||0)
        return opEx + otherEx
      }}),
  R('noi',      'Net Operating Income',  'NOI',
      { compute: m => {
        const rental = (m.MarketRent||0)+(m.LTL||0)+(m.Vacancy||0)+(m.Concessions||0)+(m.BadDebt||0)
        const totalIncome = rental + (m.RUBSInc||0) + (m.RetailInc||0) + (m.OtherInc||0)
        const opEx = (m.Payroll||0)+(m.MgmtFee||0)+(m.Landscaping||0)+(m.Repairs||0)+
                     (m.Turnover||0)+(m.Utilities||0)+(m.SecurityLife||0)+(m.Advert||0)+(m.Admin||0)
        const otherEx = (m.Insurance||0)+(m.PropTax||0)+(m.MiscExp||0)+(m.CapEx||0)
        return totalIncome - opEx - otherEx
      }}),
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getRawValue(rowDef, rawMetrics) {
  if (!rawMetrics) return null
  if (rowDef.compute) return rowDef.compute(rawMetrics)
  return rawMetrics[rowDef.key] ?? null
}

function scaleValue(raw, viewMode, numUnits) {
  if (raw == null) return null
  if (viewMode === 'per_unit_yr') return numUnits ? raw / numUnits : null
  if (viewMode === 'per_unit_mo') return numUnits ? raw / numUnits / 12 : null
  return raw
}

function formatNum(value, rowType, viewMode) {
  if (value == null) return '-'
  if (rowType === 'pct') return `${(value * 100).toFixed(1)}%`
  if (viewMode === 'per_unit_mo' && Math.abs(value) < 100) {
    return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  return Math.round(value).toLocaleString('en-US')
}

function median(arr) {
  const valid = arr.filter(v => v != null && !isNaN(v)).sort((a, b) => a - b)
  if (!valid.length) return null
  const mid = Math.floor(valid.length / 2)
  return valid.length % 2 ? valid[mid] : (valid[mid - 1] + valid[mid]) / 2
}

function cellColor(value, med, isIncome) {
  if (value == null || med == null || med === 0) return ''
  const pct = (value - med) / Math.abs(med)
  if (isIncome) {
    if (pct > 0.15) return 'bg-green-50 text-green-800'
    if (pct < -0.15) return 'bg-red-50 text-red-800'
  } else {
    if (pct > 0.15) return 'bg-red-50 text-red-800'
    if (pct < -0.15) return 'bg-green-50 text-green-800'
  }
  return ''
}

// ---------------------------------------------------------------------------
// Comp Selector
// ---------------------------------------------------------------------------

function CompSelector({ allComps, selected, onToggle }) {
  const [search, setSearch] = useState('')

  const filtered = useMemo(() =>
    allComps.filter(c =>
      c.property_name.toLowerCase().includes(search.toLowerCase()) ||
      (c.city || '').toLowerCase().includes(search.toLowerCase())
    ),
    [allComps, search]
  )

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">Comp Properties (max 4)</h3>
        {selected.length > 0 && (
          <span className="text-xs text-gray-500">{selected.length} selected</span>
        )}
      </div>

      {/* Selected chips */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {selected.map(c => (
            <span key={c.id} className="flex items-center gap-1 px-2.5 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
              {c.property_name}
              <button onClick={() => onToggle(c)} className="ml-0.5 hover:text-blue-600">
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Search */}
      <div className="relative mb-2">
        <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-gray-400" />
        <input
          type="text"
          placeholder="Search comps..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-8 pr-3 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      {allComps.length === 0 ? (
        <p className="text-xs text-gray-400 text-center py-3">
          No comps available. Import an Expense Comp File from Admin → Knowledge Base.
        </p>
      ) : (
        <div className="max-h-40 overflow-y-auto space-y-1">
          {filtered.map(c => {
            const isSelected = selected.some(s => s.id === c.id)
            const disabled = !isSelected && selected.length >= 4
            return (
              <button
                key={c.id}
                onClick={() => !disabled && onToggle(c)}
                disabled={disabled}
                className={`w-full text-left px-3 py-1.5 rounded-md text-xs transition-colors ${
                  isSelected ? 'bg-blue-600 text-white' :
                  disabled ? 'opacity-40 cursor-not-allowed text-gray-600' :
                  'hover:bg-gray-100 text-gray-700'
                }`}
              >
                <span className="font-medium">{c.property_name}</span>
                <span className="ml-2 opacity-75">
                  {[c.num_units && `${c.num_units}u`, c.year_built, c.financial_stmt_year].filter(Boolean).join(' · ')}
                </span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Grid
// ---------------------------------------------------------------------------

function Grid({ subject, selectedComps, viewMode }) {
  // Build list of columns: each period of subject + each comp
  const subjectCols = subject?.periods?.length
    ? subject.periods.map((p, i) => ({
        key: `subject-${i}`,
        header: {
          name: subject.name,
          numUnits: subject.num_units,
          yearBuilt: subject.year_built,
          avgSf: subject.avg_sf,
          stmtYear: p.label,
          stmtType: p.stmt_type,
        },
        metrics: p.metrics,
        numUnits: subject.num_units,
        isSubject: true,
      }))
    : [{
        key: 'subject-0',
        header: {
          name: subject?.name || 'Subject',
          numUnits: subject?.num_units,
          yearBuilt: null,
          avgSf: null,
          stmtYear: 'T12',
          stmtType: '—',
        },
        metrics: {},
        numUnits: subject?.num_units,
        isSubject: true,
      }]

  const compCols = selectedComps.map((c, i) => ({
    key: `comp-${i}`,
    header: {
      name: c.property_name,
      numUnits: c.num_units,
      yearBuilt: c.year_built,
      avgSf: c.avg_sf,
      stmtYear: c.financial_stmt_year,
      stmtType: c.financial_stmt_type,
    },
    metrics: c.metrics || {},
    numUnits: c.num_units,
    isSubject: false,
  }))

  const allCols = [...subjectCols, ...compCols]

  // Pre-compute display values for every cell so we can calculate medians
  const displayValues = useMemo(() => {
    const result = {}
    ROW_DEFS.forEach(row => {
      if (row.type === 'section') return
      result[row.key] = allCols.map(col => {
        if (row.type === 'pct') {
          return row.compute ? row.compute(col.metrics) : null
        }
        const raw = getRawValue(row, col.metrics)
        return scaleValue(raw, viewMode, col.numUnits)
      })
    })
    return result
  }, [allCols, viewMode])

  const PROP_HEADERS = [
    { label: 'Year Built',  key: 'yearBuilt' },
    { label: '# Units',    key: 'numUnits' },
    { label: 'Avg SF',     key: 'avgSf',   fmt: v => v ? v.toFixed(0) : '—' },
    { label: 'Stmt Year',  key: 'stmtYear' },
    { label: 'Stmt Type',  key: 'stmtType' },
  ]

  const COL_W = 'min-w-[140px] w-40'

  return (
    <div className="overflow-x-auto border border-gray-200 rounded-xl">
      <table className="text-xs border-collapse" style={{ minWidth: 'max-content' }}>
        <thead>
          {/* Property name row */}
          <tr className="bg-gray-800 text-white">
            <th className="sticky left-0 z-20 bg-gray-800 text-left px-4 py-2.5 font-semibold w-52">
              Property
            </th>
            {allCols.map(col => (
              <th key={col.key} className={`${COL_W} px-3 py-2.5 text-center font-semibold border-l border-gray-700 ${col.isSubject ? 'bg-blue-900' : ''}`}>
                <div className="truncate max-w-[136px]" title={col.header.name}>{col.header.name}</div>
                <div className="text-gray-400 font-normal text-[10px]">($)</div>
              </th>
            ))}
          </tr>
          {/* Property attribute rows */}
          {PROP_HEADERS.map(ph => (
            <tr key={ph.key} className="bg-gray-100 border-b border-gray-200">
              <td className="sticky left-0 z-20 bg-gray-100 px-4 py-1 text-gray-500 font-medium w-52">{ph.label}</td>
              {allCols.map(col => (
                <td key={col.key} className={`${COL_W} px-3 py-1 text-center text-gray-700 border-l border-gray-200 ${col.isSubject ? 'bg-blue-50' : ''}`}>
                  {ph.fmt ? ph.fmt(col.header[ph.key]) : (col.header[ph.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {ROW_DEFS.map((row, ri) => {
            if (row.type === 'section') {
              return (
                <tr key={ri} className="bg-gray-200">
                  <td className="sticky left-0 z-20 bg-gray-200 px-4 py-1.5 font-bold text-gray-700 uppercase tracking-wide w-52" colSpan={allCols.length + 1}>
                    {row.label}
                  </td>
                </tr>
              )
            }

            const values = displayValues[row.key] || []
            const med = median(values)

            const isSubtotalRow = row.type === 'subtotal'
            const isTotalRow    = row.type === 'total'
            const isNOIRow      = row.type === 'noi'
            const isPctRow      = row.type === 'pct'

            const rowBg = isNOIRow      ? 'bg-gray-800'
                        : isTotalRow    ? 'bg-gray-200'
                        : isSubtotalRow ? 'bg-gray-100'
                        : 'bg-white hover:bg-gray-50'
            const labelStyle = isNOIRow   ? 'text-white font-bold'
                             : isTotalRow || isSubtotalRow ? 'text-gray-800 font-semibold'
                             : 'text-gray-700'

            return (
              <tr key={ri} className={`border-b border-gray-100 ${rowBg}`}>
                <td className={`sticky left-0 z-20 px-4 py-1.5 w-52 ${rowBg} ${labelStyle} ${isPctRow ? 'pl-6 italic' : ''}`}>
                  {row.label}
                </td>
                {allCols.map((col, ci) => {
                  const displayVal = values[ci]
                  const formatted = formatNum(displayVal, row.type, viewMode)

                  let colorClass = ''
                  if (!isNOIRow && !isPctRow && !isTotalRow && !isSubtotalRow) {
                    colorClass = cellColor(displayVal, med, row.isIncome)
                  }

                  const noiBg = isNOIRow && col.isSubject ? 'bg-blue-900' : isNOIRow ? 'bg-gray-800' : ''
                  const noiFg = isNOIRow
                    ? (displayVal != null && displayVal >= 0 ? 'text-green-400 font-bold' : 'text-red-400 font-bold')
                    : ''

                  return (
                    <td
                      key={col.key}
                      className={`${COL_W} px-3 py-1.5 text-right border-l border-gray-200
                        ${col.isSubject && !isNOIRow ? 'bg-blue-50' : ''}
                        ${noiBg} ${noiFg} ${colorClass}
                        ${(isTotalRow || isSubtotalRow) ? 'font-semibold' : ''}
                      `}
                    >
                      {formatted}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const VIEW_MODES = [
  { id: 'total',       label: 'Total' },
  { id: 'per_unit_yr', label: 'Per Unit / Year' },
  { id: 'per_unit_mo', label: 'Per Unit / Month' },
]

export default function IncExpVar() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [selectedComps, setSelectedComps] = useState([])
  const [viewMode, setViewMode] = useState('total')

  const compIds = selectedComps.map(c => c.id)

  const { data: compData, isLoading } = useQuery({
    queryKey: ['comparison', id, compIds.join(',')],
    queryFn: () => expenseCompsApi.getComparison(id, compIds).then(r => r.data),
  })

  const { data: allCompsData } = useQuery({
    queryKey: ['expense-comps'],
    queryFn: () => expenseCompsApi.list().then(r => r.data).catch(() => []),
  })

  const allComps = allCompsData || []

  const toggleComp = (comp) => {
    setSelectedComps(prev =>
      prev.some(c => c.id === comp.id)
        ? prev.filter(c => c.id !== comp.id)
        : prev.length < 4 ? [...prev, comp] : prev
    )
  }

  return (
    <div className="max-w-screen-2xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate(`/deals/${id}`)} className="p-1.5 hover:bg-gray-100 rounded-md">
          <ArrowLeft className="h-5 w-5 text-gray-600" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-gray-900">
            {compData?.subject?.name || 'Comparison'}
          </h1>
          <p className="text-sm text-gray-500">Inc-Exp Var — Comp Analysis</p>
        </div>
        <div className="ml-auto flex gap-1 bg-gray-100 rounded-lg p-1">
          {VIEW_MODES.map(vm => (
            <button
              key={vm.id}
              onClick={() => setViewMode(vm.id)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                viewMode === vm.id ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {vm.label}
            </button>
          ))}
        </div>
      </div>

      {/* Comp selector */}
      <CompSelector allComps={allComps} selected={selectedComps} onToggle={toggleComp} />

      {/* Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : (
        <Grid
          subject={compData?.subject}
          selectedComps={compData?.comps || []}
          viewMode={viewMode}
        />
      )}
    </div>
  )
}
