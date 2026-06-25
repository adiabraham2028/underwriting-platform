import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Building2, Map, Users, LogOut, GitCompare } from 'lucide-react'

export default function Navbar() {
  const { currentUser, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="bg-white border-b border-gray-200 h-16 flex items-center px-6 gap-6">
      <Link to="/" className="flex items-center gap-2 font-semibold text-blue-700">
        <Building2 className="h-6 w-6" />
        <span>Underwriting Platform</span>
      </Link>
      <div className="flex-1 flex items-center gap-4">
        <Link to="/" className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1.5">
          <Building2 className="h-4 w-4" />
          Deals
        </Link>
        <Link to="/map" className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1.5">
          <Map className="h-4 w-4" />
          Portfolio Map
        </Link>
        <Link to="/compare" className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1.5">
          <GitCompare className="h-4 w-4" />
          Compare
        </Link>
        {currentUser?.role === 'admin' && (
          <Link to="/admin" className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1.5">
            <Users className="h-4 w-4" />
            Admin
          </Link>
        )}
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-600">{currentUser?.full_name}</span>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${currentUser?.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-700'}`}>
          {currentUser?.role}
        </span>
        <button onClick={handleLogout} className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-md" title="Logout">
          <LogOut className="h-5 w-5" />
        </button>
      </div>
    </nav>
  )
}
