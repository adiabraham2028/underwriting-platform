import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import { DealProvider } from './context/DealContext'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import DealDetail from './pages/DealDetail'
import ModelEditor from './pages/ModelEditor'
import DealComparison from './pages/DealComparison'
import Admin from './pages/Admin'
import ClassificationReview from './pages/ClassificationReview'
import ClientTemplate from './pages/ClientTemplate'
import IncExpVar from './pages/IncExpVar'
import PortfolioMap from './pages/PortfolioMap'
import Navbar from './components/Navbar'
import AIChat from './components/AIChat'

function ProtectedRoute({ children, adminOnly = false }) {
  const { isAuthenticated, isLoading, currentUser } = useAuth()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (adminOnly && currentUser?.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <DealProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <div className="min-h-screen bg-gray-50">
                  <Navbar />
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/map" element={<PortfolioMap />} />
                    <Route path="/deals/:id" element={<DealDetail />} />
                    <Route path="/deals/:id/model" element={<ModelEditor />} />
                    <Route path="/deals/:id/classify" element={<ClassificationReview />} />
                    <Route path="/deals/:id/inc-exp-var" element={<IncExpVar />} />
                    <Route path="/deals/:id/comparison" element={<IncExpVar />} />
                    <Route path="/compare" element={<DealComparison />} />
                    <Route
                      path="/admin"
                      element={
                        <ProtectedRoute adminOnly>
                          <Admin />
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path="/admin/template"
                      element={
                        <ProtectedRoute adminOnly>
                          <ClientTemplate />
                        </ProtectedRoute>
                      }
                    />
                  </Routes>
                  <AIChat />
                </div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </DealProvider>
    </BrowserRouter>
  )
}
