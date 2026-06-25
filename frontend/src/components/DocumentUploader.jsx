import { useState, useRef } from 'react'
import { documentsApi } from '../api/documents'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import ProcessingStatus from './ProcessingStatus'
import { Upload, FileText, X, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import toast from 'react-hot-toast'

const DOC_TYPES = [
  { value: 'rent_roll', label: 'Rent Roll' },
  { value: 't12', label: 'T-12 Operating Statement' },
  { value: 'om', label: 'Offering Memorandum' },
  { value: 'other', label: 'Other' },
]

export default function DocumentUploader({ dealId, onUploaded }) {
  const queryClient = useQueryClient()
  const [dragOver, setDragOver] = useState(false)
  const [docType, setDocType] = useState('rent_roll')
  const [uploading, setUploading] = useState(false)
  const [processingDocId, setProcessingDocId] = useState(null)
  const fileInputRef = useRef(null)

  const { data: documents = [], refetch } = useQuery({
    queryKey: ['documents', dealId],
    queryFn: () => documentsApi.list(dealId).then(r => r.data),
  })

  const handleUpload = async (file) => {
    if (!file) return
    setUploading(true)
    try {
      const res = await documentsApi.upload(dealId, file, docType)
      toast.success('Document uploaded, processing...')
      setProcessingDocId(res.data.id)
      refetch()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleUpload(file)
  }

  const handleFileInput = (e) => {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
    e.target.value = ''
  }

  const handleDelete = async (docId) => {
    try {
      await documentsApi.delete(dealId, docId)
      toast.success('Document deleted')
      refetch()
    } catch {
      toast.error('Failed to delete document')
    }
  }

  const statusIcon = (status) => {
    switch (status) {
      case 'complete': return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failed': return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'processing': return <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
      default: return <Clock className="h-4 w-4 text-gray-400" />
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-900 mb-4">Upload Document</h3>
        <div className="mb-3">
          <label className="block text-sm font-medium text-gray-700 mb-1">Document Type</label>
          <select value={docType} onChange={e => setDocType(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
            {DOC_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => !uploading && fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
          } ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          <Upload className="h-8 w-8 text-gray-400 mx-auto mb-2" />
          <p className="text-sm text-gray-600">
            {uploading ? 'Uploading...' : 'Drop file here or click to browse'}
          </p>
          <p className="text-xs text-gray-400 mt-1">PDF, XLSX, DOCX supported</p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.xlsx,.xls,.docx"
            onChange={handleFileInput}
            className="hidden"
          />
        </div>
      </div>

      {processingDocId && (
        <ProcessingStatus
          dealId={dealId}
          docId={processingDocId}
          onComplete={() => {
            setProcessingDocId(null)
            refetch()
            onUploaded?.()
          }}
        />
      )}

      {documents.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="font-semibold text-gray-900 text-sm">Documents</h3>
          </div>
          <ul className="divide-y divide-gray-100">
            {documents.map(doc => (
              <li key={doc.id} className="flex items-center gap-3 px-5 py-3">
                <FileText className="h-4 w-4 text-gray-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{doc.file_name}</p>
                  <p className="text-xs text-gray-500">
                    {DOC_TYPES.find(t => t.value === doc.document_type)?.label} • {doc.file_format}
                  </p>
                </div>
                {statusIcon(doc.extraction_status)}
                {doc.extraction_error && (
                  <span className="text-xs text-red-500 truncate max-w-32" title={doc.extraction_error}>
                    {doc.extraction_error}
                  </span>
                )}
                <button onClick={() => handleDelete(doc.id)} className="p-1 text-gray-400 hover:text-red-500">
                  <X className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
