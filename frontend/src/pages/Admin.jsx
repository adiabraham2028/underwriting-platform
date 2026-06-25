import { useState } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { templatesApi } from '../api/templates'
import { knowledgeBaseApi } from '../api/knowledge_base'
import client from '../api/client'
import toast from 'react-hot-toast'
import { Upload, Star, Users, FileSpreadsheet, Database, RefreshCw, ExternalLink } from 'lucide-react'

export default function Admin() {
  const [activeSection, setActiveSection] = useState('templates')

  const sections = [
    { id: 'templates', label: 'Templates', icon: FileSpreadsheet },
    { id: 'knowledge-base', label: 'Knowledge Base', icon: Database },
    { id: 'users', label: 'Users', icon: Users },
  ]

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Admin</h1>
      <div className="flex gap-4 mb-8">
        {sections.map(s => (
          <button
            key={s.id}
            onClick={() => setActiveSection(s.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium ${activeSection === s.id ? 'bg-blue-600 text-white' : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'}`}
          >
            <s.icon className="h-4 w-4" />
            {s.label}
          </button>
        ))}
      </div>
      {activeSection === 'templates' && <TemplateSection />}
      {activeSection === 'knowledge-base' && <KnowledgeBaseSection />}
      {activeSection === 'users' && <UserSection />}
    </div>
  )
}

function KnowledgeBaseSection() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['kb-stats'],
    queryFn: () => knowledgeBaseApi.stats().then(r => r.data).catch(() => null),
  })

  const { data: classifications = [] } = useQuery({
    queryKey: ['kb-list'],
    queryFn: () => knowledgeBaseApi.list(0, 100).then(r => r.data).catch(() => []),
  })

  const seedMutation = useMutation({
    mutationFn: () => knowledgeBaseApi.seed(),
    onSuccess: (res) => {
      toast.success(`Seed complete: ${res.data.added} new entries added`)
      queryClient.invalidateQueries(['kb-stats'])
      queryClient.invalidateQueries(['kb-list'])
    },
    onError: () => toast.error('Seed failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => knowledgeBaseApi.delete(id),
    onSuccess: () => {
      toast.success('Mapping deleted')
      queryClient.invalidateQueries(['kb-stats'])
      queryClient.invalidateQueries(['kb-list'])
    },
    onError: () => toast.error('Delete failed'),
  })

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Total Mappings</p>
          <p className="text-3xl font-bold text-gray-900">{statsLoading ? '...' : (stats?.total ?? 0)}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Auto-Classifiable</p>
          <p className="text-3xl font-bold text-blue-600">{statsLoading ? '...' : `${stats?.auto_classifiable_pct ?? 0}%`}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Human Corrections (30d)</p>
          <p className="text-3xl font-bold text-purple-600">{statsLoading ? '...' : (stats?.corrected_last_30d ?? 0)}</p>
        </div>
      </div>

      {/* Actions row */}
      <div className="flex gap-3">
        <button
          onClick={() => seedMutation.mutate()}
          disabled={seedMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 text-sm rounded-md hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${seedMutation.isPending ? 'animate-spin' : ''}`} />
          {seedMutation.isPending ? 'Seeding...' : 'Re-seed Default Classifications'}
        </button>
        <button
          onClick={() => navigate('/admin/template')}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
        >
          <ExternalLink className="h-4 w-4" />
          Manage Client Template
        </button>
      </div>

      {/* Classifications table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold">Classification Mappings</h2>
          <p className="text-sm text-gray-500 mt-0.5">Showing first 100 mappings</p>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-4 py-3 font-medium text-gray-700">Line Item</th>
              <th className="text-left px-4 py-3 font-medium text-gray-700">Account Code</th>
              <th className="text-left px-4 py-3 font-medium text-gray-700">Category</th>
              <th className="text-left px-4 py-3 font-medium text-gray-700">Source</th>
              <th className="text-left px-4 py-3 font-medium text-gray-700">Confidence</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {classifications.map(c => (
              <tr key={c.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-2.5 font-medium text-gray-900 text-xs">{c.original_line_item}</td>
                <td className="px-4 py-2.5 text-gray-500 font-mono text-xs">{c.account_code || '-'}</td>
                <td className="px-4 py-2.5">
                  <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full">{c.assigned_category}</span>
                </td>
                <td className="px-4 py-2.5">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${
                    c.classification_source === 'human' ? 'bg-purple-100 text-purple-700' :
                    c.classification_source === 'ai' ? 'bg-green-100 text-green-700' :
                    'bg-gray-100 text-gray-600'
                  }`}>
                    {c.classification_source}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-gray-600 text-xs">{Math.round(c.confidence * 100)}%</td>
                <td className="px-4 py-2.5 text-right">
                  {c.classification_source !== 'seed' && (
                    <button
                      onClick={() => deleteMutation.mutate(c.id)}
                      className="text-red-500 hover:text-red-700 text-xs"
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {classifications.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  No classifications yet. Run seed to populate defaults.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function TemplateSection() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [uploadName, setUploadName] = useState('')
  const [uploadFile, setUploadFile] = useState(null)
  const [uploading, setUploading] = useState(false)

  const { data: templates = [], error: templatesError } = useQuery({
    queryKey: ['templates'],
    queryFn: () => templatesApi.list().then(r => r.data),
  })

  if (templatesError) console.error('Templates fetch failed:', templatesError?.response?.data || templatesError.message)

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!uploadFile || !uploadName) return
    setUploading(true)
    try {
      await templatesApi.upload(uploadFile, uploadName)
      toast.success('Template uploaded')
      queryClient.invalidateQueries(['templates'])
      setUploadName('')
      setUploadFile(null)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleSetDefault = async (id) => {
    try {
      await templatesApi.setDefault(id)
      toast.success('Default template updated')
      queryClient.invalidateQueries(['templates'])
    } catch {
      toast.error('Failed to set default')
    }
  }

  return (
    <div className="space-y-6">
      {/* Client template link */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-blue-900">Client-Specific Template</p>
          <p className="text-xs text-blue-700">Upload and manage your .xlsm template with cell mappings</p>
        </div>
        <button
          onClick={() => navigate('/admin/template')}
          className="flex items-center gap-2 px-3 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
        >
          <ExternalLink className="h-4 w-4" />
          Manage Client Template
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold mb-4">Upload New Template</h2>
        <form onSubmit={handleUpload} className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Template Name</label>
            <input type="text" value={uploadName} onChange={e => setUploadName(e.target.value)} required
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Excel File (.xlsx / .xlsm)</label>
            <input type="file" accept=".xlsx,.xlsm" onChange={e => setUploadFile(e.target.files?.[0] || null)} required
              className="w-full text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
          </div>
          <button type="submit" disabled={uploading} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50">
            <Upload className="h-4 w-4" />
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
        </form>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold">Templates</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-6 py-3 font-medium text-gray-700">Name</th>
              <th className="text-left px-6 py-3 font-medium text-gray-700">Version</th>
              <th className="text-left px-6 py-3 font-medium text-gray-700">Created</th>
              <th className="text-left px-6 py-3 font-medium text-gray-700">Default</th>
              <th className="px-6 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {templates.map(t => (
              <tr key={t.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-6 py-3 font-medium text-gray-900">{t.name}</td>
                <td className="px-6 py-3 text-gray-600">v{t.version}</td>
                <td className="px-6 py-3 text-gray-600">{new Date(t.created_at).toLocaleDateString()}</td>
                <td className="px-6 py-3">
                  {t.is_default && <span className="flex items-center gap-1 text-yellow-600"><Star className="h-4 w-4 fill-yellow-400" />Default</span>}
                </td>
                <td className="px-6 py-3 text-right">
                  {!t.is_default && (
                    <button onClick={() => handleSetDefault(t.id)} className="text-blue-600 hover:text-blue-800 text-sm font-medium">
                      Set as Default
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {templates.length === 0 && (
              <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-400">No templates yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function UserSection() {
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ email: '', full_name: '', password: '', role: 'analyst' })
  const [creating, setCreating] = useState(false)

  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => client.get('/auth/users').then(r => r.data).catch(() => []),
  })

  const handleCreate = async (e) => {
    e.preventDefault()
    setCreating(true)
    try {
      await client.post('/auth/register', form)
      toast.success('User created')
      queryClient.invalidateQueries(['users'])
      setShowCreate(false)
      setForm({ email: '', full_name: '', password: '', role: 'analyst' })
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create user')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
        >
          Create User
        </button>
      </div>

      {showCreate && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-4">Create New User</h2>
          <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
              <input type="text" required value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input type="email" required value={form.email} onChange={e => setForm({...form, email: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input type="password" required value={form.password} onChange={e => setForm({...form, password: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
              <select value={form.role} onChange={e => setForm({...form, role: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500">
                <option value="analyst">Analyst</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="col-span-2 flex justify-end gap-3">
              <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50">Cancel</button>
              <button type="submit" disabled={creating} className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50">
                {creating ? 'Creating...' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold">Users</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-6 py-3 font-medium text-gray-700">Name</th>
              <th className="text-left px-6 py-3 font-medium text-gray-700">Email</th>
              <th className="text-left px-6 py-3 font-medium text-gray-700">Role</th>
              <th className="text-left px-6 py-3 font-medium text-gray-700">Status</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-b border-gray-100">
                <td className="px-6 py-3 font-medium text-gray-900">{u.full_name}</td>
                <td className="px-6 py-3 text-gray-600">{u.email}</td>
                <td className="px-6 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${u.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-700'}`}>
                    {u.role}
                  </span>
                </td>
                <td className="px-6 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${u.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr><td colSpan={4} className="px-6 py-8 text-center text-gray-400">No users found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
