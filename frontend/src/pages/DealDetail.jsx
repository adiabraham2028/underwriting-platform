import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { dealsApi } from '../api/deals'
import { classificationApi } from '../api/classification'
import DocumentUploader from '../components/DocumentUploader'
import FlagsPanel from '../components/FlagsPanel'
import ModelReview from '../components/ModelReview'
import TemplateOutdatedBanner from '../components/TemplateOutdatedBanner'
import { ArrowLeft, FileText, BarChart2, Flag, ClipboardCheck, TrendingUp } from 'lucide-react'

export default function DealDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('documents')

  const { data: deal, isLoading } = useQuery({
    queryKey: ['deal', id],
    queryFn: () => dealsApi.get(id).then(r => r.data),
  })

  const { data: flags = [] } = useQuery({
    queryKey: ['flags', id],
    queryFn: () => dealsApi.getFlags(id).then(r => r.data),
  })

  const { data: classificationSession } = useQuery({
    queryKey: ['classification-session', id],
    queryFn: () => classificationApi.getSession(id).then(r => r.data).catch(() => null),
    retry: false,
  })

  if (isLoading) {
    return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div></div>
  }

  if (!deal) return <div className="p-6 text-red-500">Deal not found</div>

  const hasPendingClassification = classificationSession &&
    (classificationSession.status === 'pending_review' || classificationSession.status === 'approved')

  const tabs = [
    { id: 'documents', label: 'Documents', icon: FileText },
    { id: 'model', label: 'Model', icon: BarChart2 },
    { id: 'flags', label: `Flags (${flags.filter(f => !f.resolved).length})`, icon: Flag },
    { id: 'comparison', label: 'Comparison', icon: TrendingUp },
  ]

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => navigate('/')} className="p-1.5 hover:bg-gray-100 rounded-md">
          <ArrowLeft className="h-5 w-5 text-gray-600" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900">{deal.name}</h1>
          <p className="text-sm text-gray-500">{deal.address}, {deal.city}, {deal.state} {deal.zip_code}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${
            deal.status === 'active' ? 'bg-green-100 text-green-800' :
            deal.status === 'archived' ? 'bg-gray-100 text-gray-700' :
            'bg-blue-100 text-blue-800'
          }`}>
            {deal.status}
          </span>
        </div>
      </div>

      {deal.template_outdated && (
        <TemplateOutdatedBanner
          dealId={id}
          onMigrated={() => queryClient.invalidateQueries(['deal', id])}
          onDismiss={() => dealsApi.update(id, { template_outdated: false }).then(() => queryClient.invalidateQueries(['deal', id]))}
        />
      )}

      {/* Classification pending banner */}
      {hasPendingClassification && (
        <div className="mb-4 bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ClipboardCheck className="h-5 w-5 text-amber-600 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-900">T12 Classifications Ready for Review</p>
              <p className="text-xs text-amber-700">
                {classificationSession.needs_review} items need review &bull;{' '}
                {classificationSession.auto_accepted} auto-classified
              </p>
            </div>
          </div>
          <button
            onClick={() => navigate(`/deals/${id}/classify`)}
            className="flex items-center gap-2 px-4 py-2 bg-amber-600 text-white text-sm rounded-md hover:bg-amber-700"
          >
            <ClipboardCheck className="h-4 w-4" />
            Review Classifications
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === 'documents' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <DocumentUploader dealId={id} onUploaded={() => queryClient.invalidateQueries(['flags', id])} />
          </div>
          <div>
            <FlagsPanel dealId={id} flags={flags} onResolved={() => queryClient.invalidateQueries(['flags', id])} compact />
          </div>
        </div>
      )}

      {activeTab === 'model' && (
        <div className="h-[700px] border border-gray-200 rounded-lg overflow-hidden">
          <ModelReview
            dealId={id}
            flags={flags}
            onFlagResolved={() => queryClient.invalidateQueries(['flags', id])}
          />
        </div>
      )}


      {activeTab === 'comparison' && (
        <div className="text-center py-12 text-gray-500">
          <TrendingUp className="h-10 w-10 mx-auto mb-3 text-gray-300" />
          <p className="font-medium">Open full comparison view</p>
          <p className="text-sm mt-1">The comparison grid needs more space to display properly.</p>
          <button
            onClick={() => navigate(`/deals/${id}/inc-exp-var`)}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
          >
            <TrendingUp className="h-4 w-4" />
            Open Inc-Exp Var Comparison
          </button>
        </div>
      )}
    </div>
  )
}
