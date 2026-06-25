import { useQuery } from '@tanstack/react-query'
import { dealsApi } from '../api/deals'
import DealMap from '../components/DealMap'
import { useNavigate } from 'react-router-dom'

export default function PortfolioMap() {
  const navigate = useNavigate()

  const { data: deals = [], isLoading } = useQuery({
    queryKey: ['deals'],
    queryFn: () => dealsApi.list().then(r => r.data),
  })

  return (
    <div style={{ height: 'calc(100vh - 64px)' }}>
      {isLoading ? (
        <div className="flex items-center justify-center h-full text-gray-500">Loading map...</div>
      ) : (
        <DealMap deals={deals} onDealClick={d => navigate(`/deals/${d.id}`)} />
      )}
    </div>
  )
}
