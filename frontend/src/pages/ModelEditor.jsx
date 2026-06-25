import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { dealsApi } from '../api/deals'
import SpreadsheetEditor from '../components/SpreadsheetEditor'
import FlagsPanel from '../components/FlagsPanel'
import SnapshotHistory from '../components/SnapshotHistory'
import { ArrowLeft, Download, PanelRight } from 'lucide-react'
import toast from 'react-hot-toast'

export default function ModelEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showFlags, setShowFlags] = useState(true)
  const [selectedSnapshot, setSelectedSnapshot] = useState(null)
  const [saving, setSaving] = useState(false)

  const { data: deal } = useQuery({
    queryKey: ['deal', id],
    queryFn: () => dealsApi.get(id).then(r => r.data),
  })

  const { data: modelData } = useQuery({
    queryKey: ['model', id, selectedSnapshot],
    queryFn: () => dealsApi.getModel(id, selectedSnapshot).then(r => r.data),
  })

  const { data: flags = [] } = useQuery({
    queryKey: ['flags', id],
    queryFn: () => dealsApi.getFlags(id).then(r => r.data),
  })

  const handleSave = async (luckysheetJson) => {
    setSaving(true)
    try {
      await dealsApi.saveModel(id, { luckysheet_json: luckysheetJson })
      toast.success('Model saved')
      queryClient.invalidateQueries(['model', id])
    } catch {
      toast.error('Failed to save model')
    } finally {
      setSaving(false)
    }
  }

  const handleExport = async () => {
    try {
      const res = await dealsApi.exportModel(id)
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `${deal?.name || 'model'}_model.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Export failed')
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-3 bg-white border-b border-gray-200">
        <button onClick={() => navigate(`/deals/${id}`)} className="p-1.5 hover:bg-gray-100 rounded-md">
          <ArrowLeft className="h-5 w-5 text-gray-600" />
        </button>
        <div className="flex-1">
          <span className="font-semibold text-gray-900">{deal?.name}</span>
          <span className="text-sm text-gray-500 ml-2">Model Editor</span>
        </div>
        <SnapshotHistory dealId={id} selected={selectedSnapshot} onSelect={setSelectedSnapshot} />
        <button
          onClick={handleExport}
          className="flex items-center gap-2 px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
        >
          <Download className="h-4 w-4" />
          Export Excel
        </button>
        <button
          onClick={() => setShowFlags(!showFlags)}
          className={`p-1.5 rounded-md ${showFlags ? 'bg-blue-50 text-blue-600' : 'hover:bg-gray-100 text-gray-600'}`}
        >
          <PanelRight className="h-5 w-5" />
        </button>
        {saving && <span className="text-sm text-gray-500">Saving...</span>}
      </div>

      {/* Editor + Flags */}
      <div className="flex flex-1 overflow-hidden">
        <div className={`flex-1 overflow-hidden ${showFlags ? 'mr-0' : ''}`}>
          <SpreadsheetEditor
            dealId={id}
            luckysheetData={modelData?.luckysheet_json}
            flags={flags}
            onSave={handleSave}
            fullScreen
          />
        </div>
        {showFlags && (
          <div className="w-80 border-l border-gray-200 overflow-y-auto bg-white">
            <FlagsPanel
              dealId={id}
              flags={flags}
              onResolved={() => queryClient.invalidateQueries(['flags', id])}
              compact
            />
          </div>
        )}
      </div>
    </div>
  )
}
