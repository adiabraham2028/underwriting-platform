import { MapPin, Home, Flag, Clock } from 'lucide-react'

export default function DealCard({ deal, onClick }) {
  const flagCount = deal.flag_count || 0
  const statusColors = {
    active: 'bg-green-100 text-green-800',
    archived: 'bg-gray-100 text-gray-700',
    closed: 'bg-blue-100 text-blue-800',
  }

  return (
    <div
      onClick={onClick}
      className="bg-white rounded-lg border border-gray-200 p-4 cursor-pointer hover:border-blue-300 hover:shadow-sm transition-all"
    >
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-semibold text-gray-900 text-sm leading-tight flex-1 mr-2">{deal.name}</h3>
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0 ${statusColors[deal.status] || 'bg-gray-100 text-gray-700'}`}>
          {deal.status}
        </span>
      </div>
      <div className="flex items-center gap-1 text-xs text-gray-500 mb-3">
        <MapPin className="h-3 w-3" />
        {deal.city}, {deal.state} {deal.zip_code}
      </div>
      <div className="flex items-center gap-4 text-xs text-gray-600">
        {deal.total_units && (
          <span className="flex items-center gap-1">
            <Home className="h-3.5 w-3.5" />
            {deal.total_units} units
          </span>
        )}
        {flagCount > 0 && (
          <span className="flex items-center gap-1 text-amber-600">
            <Flag className="h-3.5 w-3.5" />
            {flagCount} flag{flagCount !== 1 ? 's' : ''}
          </span>
        )}
        <span className="flex items-center gap-1 ml-auto text-gray-400">
          <Clock className="h-3 w-3" />
          {new Date(deal.last_updated).toLocaleDateString()}
        </span>
      </div>
    </div>
  )
}
