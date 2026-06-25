import { useQuery } from '@tanstack/react-query'
import { dealsApi } from '../api/deals'
import { History } from 'lucide-react'

export default function SnapshotHistory({ dealId, selected, onSelect }) {
  const { data: snapshots = [] } = useQuery({
    queryKey: ['snapshots', dealId],
    queryFn: () => dealsApi.getSnapshots(dealId).then(r => r.data),
  })

  if (snapshots.length === 0) return null

  return (
    <div className="flex items-center gap-2">
      <History className="h-4 w-4 text-gray-500" />
      <select
        value={selected || ''}
        onChange={e => onSelect(e.target.value || null)}
        className="py-1.5 px-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500"
      >
        <option value="">Latest snapshot</option>
        {snapshots.map(s => (
          <option key={s.id} value={s.id}>
            {s.snapshot_name} — {new Date(s.created_at).toLocaleDateString()}
          </option>
        ))}
      </select>
    </div>
  )
}
