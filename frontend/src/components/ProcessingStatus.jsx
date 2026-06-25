import { useEffect, useState, useRef } from 'react'
import { documentsApi } from '../api/documents'
import { CheckCircle, AlertCircle, Loader } from 'lucide-react'

const STATUS_MESSAGES = {
  pending: 'Queued for processing...',
  processing: 'Extracting data with AI...',
  complete: 'Processing complete!',
  failed: 'Processing failed.',
}

export default function ProcessingStatus({ dealId, docId, onComplete }) {
  const [status, setStatus] = useState('pending')
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await documentsApi.getStatus(dealId, docId)
        const { status: s, error: e } = res.data
        setStatus(s)
        if (e) setError(e)

        if (s === 'complete' || s === 'failed') {
          clearInterval(intervalRef.current)
          if (s === 'complete') onComplete?.()
        }
      } catch {
        clearInterval(intervalRef.current)
      }
    }

    poll()
    intervalRef.current = setInterval(poll, 2000)
    return () => clearInterval(intervalRef.current)
  }, [dealId, docId, onComplete])

  const icon = status === 'complete'
    ? <CheckCircle className="h-5 w-5 text-green-500" />
    : status === 'failed'
    ? <AlertCircle className="h-5 w-5 text-red-500" />
    : <Loader className="h-5 w-5 text-blue-500 animate-spin" />

  const bgColor = status === 'complete' ? 'bg-green-50 border-green-200' :
    status === 'failed' ? 'bg-red-50 border-red-200' :
    'bg-blue-50 border-blue-200'

  return (
    <div className={`flex items-center gap-3 p-3 rounded-lg border ${bgColor}`}>
      {icon}
      <div className="flex-1">
        <p className="text-sm font-medium text-gray-900">{STATUS_MESSAGES[status] || status}</p>
        {error && <p className="text-xs text-red-600 mt-0.5">{error}</p>}
      </div>
    </div>
  )
}
