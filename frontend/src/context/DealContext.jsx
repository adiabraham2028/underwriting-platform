import { createContext, useContext, useState } from 'react'

const DealContext = createContext(null)

export function DealProvider({ children }) {
  const [selectedDealId, setSelectedDealId] = useState(null)
  const [dealFilters, setDealFilters] = useState({ state: '', status: '' })

  return (
    <DealContext.Provider value={{ selectedDealId, setSelectedDealId, dealFilters, setDealFilters }}>
      {children}
    </DealContext.Provider>
  )
}

export function useDeal() {
  const ctx = useContext(DealContext)
  if (!ctx) throw new Error('useDeal must be used within DealProvider')
  return ctx
}
