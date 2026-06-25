import { useState } from 'react'
import { dealsApi } from '../api/deals'
import { AlertTriangle, X, RefreshCw } from 'lucide-react'
import toast from 'react-hot-toast'

export default function TemplateOutdatedBanner({ dealId, onMigrated, onDismiss }) {
  const [migrating, setMigrating] = useState(false)

  const handleMigrate = async () => {
    setMigrating(true)
    try {
      await dealsApi.migrateTemplate(dealId)
      toast.success('Template migration complete')
      onMigrated?.()
    } catch {
      toast.error('Migration failed')
    } finally {
      setMigrating(false)
    }
  }

  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-yellow-50 border border-yellow-200 rounded-lg mb-4">
      <AlertTriangle className="h-5 w-5 text-yellow-600 flex-shrink-0" />
      <p className="flex-1 text-sm text-yellow-800">
        A new default template is available. Migrate to apply the updated model structure to this deal.
      </p>
      <button
        onClick={handleMigrate}
        disabled={migrating}
        className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-yellow-800 bg-yellow-100 border border-yellow-300 rounded-md hover:bg-yellow-200 disabled:opacity-50"
      >
        <RefreshCw className={`h-3.5 w-3.5 ${migrating ? 'animate-spin' : ''}`} />
        {migrating ? 'Migrating...' : 'Migrate'}
      </button>
      <button onClick={onDismiss} className="p-1 text-yellow-600 hover:text-yellow-800">
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
