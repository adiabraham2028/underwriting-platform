import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import client from '../api/client'
import toast from 'react-hot-toast'
import { Upload, FileSpreadsheet, CheckCircle2, ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const templateApi = {
  get: () => client.get('/my/template'),
  upload: (name, file) => {
    const fd = new FormData()
    fd.append('name', name)
    fd.append('file', file)
    return client.post('/my/template', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  getMapping: () => client.get('/my/template/mapping'),
  getVersions: () => client.get('/my/template/versions'),
  activate: (id) => client.post(`/my/template/${id}/activate`),
}

export default function ClientTemplate() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [uploadName, setUploadName] = useState('')
  const [uploadFile, setUploadFile] = useState(null)

  const { data: template } = useQuery({
    queryKey: ['client-template'],
    queryFn: () => templateApi.get().then(r => r.data).catch(() => null),
  })

  const { data: mapping } = useQuery({
    queryKey: ['client-template-mapping'],
    queryFn: () => templateApi.getMapping().then(r => r.data).catch(() => null),
    enabled: !!template,
  })

  const { data: versions = [] } = useQuery({
    queryKey: ['client-template-versions'],
    queryFn: () => templateApi.getVersions().then(r => r.data).catch(() => []),
  })

  const uploadMutation = useMutation({
    mutationFn: () => templateApi.upload(uploadName, uploadFile),
    onSuccess: () => {
      toast.success('Template uploaded successfully')
      setUploadName('')
      setUploadFile(null)
      queryClient.invalidateQueries(['client-template'])
      queryClient.invalidateQueries(['client-template-versions'])
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Upload failed'),
  })

  const activateMutation = useMutation({
    mutationFn: (id) => templateApi.activate(id),
    onSuccess: () => {
      toast.success('Template version activated')
      queryClient.invalidateQueries(['client-template'])
      queryClient.invalidateQueries(['client-template-versions'])
    },
    onError: () => toast.error('Failed to activate version'),
  })

  const handleUpload = (e) => {
    e.preventDefault()
    if (!uploadName || !uploadFile) return
    uploadMutation.mutate()
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/admin')} className="p-1.5 hover:bg-gray-100 rounded-md">
          <ArrowLeft className="h-5 w-5 text-gray-600" />
        </button>
        <h1 className="text-2xl font-bold text-gray-900">Client Template</h1>
      </div>

      {/* Current template info */}
      {template ? (
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <FileSpreadsheet className="h-6 w-6 text-blue-600" />
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{template.name}</h2>
              <p className="text-sm text-gray-500">
                v{template.version} &bull; {new Date(template.created_at).toLocaleDateString()}
                {template.mapping_confirmed && (
                  <span className="ml-2 inline-flex items-center gap-1 text-green-600 text-xs">
                    <CheckCircle2 className="h-3 w-3" /> Mapping confirmed
                  </span>
                )}
              </p>
            </div>
          </div>
          {template.tab_names?.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">Sheets</p>
              <div className="flex flex-wrap gap-2">
                {template.tab_names.map(tab => (
                  <span key={tab} className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded">{tab}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6 text-sm text-yellow-800">
          No client template uploaded yet.
        </div>
      )}

      {/* Upload form */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">Upload New Template</h2>
        <form onSubmit={handleUpload} className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Template Name</label>
            <input
              type="text"
              value={uploadName}
              onChange={e => setUploadName(e.target.value)}
              required
              placeholder="e.g. Q1 2026 Underwriting Model"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Excel File (.xlsx/.xlsm)</label>
            <input
              type="file"
              accept=".xlsx,.xlsm"
              onChange={e => setUploadFile(e.target.files?.[0] || null)}
              required
              className="w-full text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
          </div>
          <button
            type="submit"
            disabled={uploadMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            <Upload className="h-4 w-4" />
            {uploadMutation.isPending ? 'Uploading...' : 'Upload'}
          </button>
        </form>
      </div>

      {/* Cell mapping viewer */}
      {mapping && Object.keys(mapping).length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold mb-3">Cell Mapping</h2>
          <pre className="text-xs bg-gray-50 rounded-lg p-4 overflow-auto max-h-64 text-gray-700">
            {JSON.stringify(mapping, null, 2)}
          </pre>
        </div>
      )}

      {/* Version history */}
      {versions.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-semibold">Version History</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-6 py-3 font-medium text-gray-700">Name</th>
                <th className="text-left px-6 py-3 font-medium text-gray-700">Version</th>
                <th className="text-left px-6 py-3 font-medium text-gray-700">Created</th>
                <th className="text-left px-6 py-3 font-medium text-gray-700">Status</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {versions.map(v => (
                <tr key={v.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-6 py-3 font-medium text-gray-900">{v.name}</td>
                  <td className="px-6 py-3 text-gray-600">v{v.version}</td>
                  <td className="px-6 py-3 text-gray-600">{new Date(v.created_at).toLocaleDateString()}</td>
                  <td className="px-6 py-3">
                    {v.is_active ? (
                      <span className="px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded-full font-medium">Active</span>
                    ) : (
                      <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">Inactive</span>
                    )}
                  </td>
                  <td className="px-6 py-3 text-right">
                    {!v.is_active && (
                      <button
                        onClick={() => activateMutation.mutate(v.id)}
                        disabled={activateMutation.isPending}
                        className="text-blue-600 hover:text-blue-800 text-sm font-medium disabled:opacity-50"
                      >
                        Activate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
