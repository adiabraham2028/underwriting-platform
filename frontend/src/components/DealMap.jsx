import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Fix leaflet default icon issue with webpack/vite
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

const greenIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
})

const grayIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-grey.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
})

export default function DealMap({ deals = [], onDealClick }) {
  const dealsWithCoords = deals.filter(d => d.lat && d.lng)

  return (
    <div className="h-full relative" style={{ position: 'relative', zIndex: 0 }}>
      <MapContainer
        center={[39.5, -98.35]}
        zoom={4}
        style={{ height: '100%', width: '100%', zIndex: 0 }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {dealsWithCoords.map(deal => (
          <Marker
            key={deal.id}
            position={[deal.lat, deal.lng]}
            icon={deal.status === 'active' ? greenIcon : grayIcon}
            eventHandlers={{ click: () => onDealClick?.(deal) }}
          >
            <Popup>
              <div className="text-sm">
                <p className="font-semibold">{deal.name}</p>
                <p className="text-gray-600">{deal.city}, {deal.state}</p>
                {deal.total_units && <p>{deal.total_units} units</p>}
                <button
                  onClick={() => onDealClick?.(deal)}
                  className="mt-2 text-blue-600 hover:underline text-xs font-medium"
                >
                  View Deal
                </button>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-6 right-4 bg-white rounded-lg shadow-md p-3 text-xs z-[1000]">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-3 h-3 rounded-full bg-green-500"></div>
          <span className="text-gray-700">Active</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-gray-400"></div>
          <span className="text-gray-700">Archived/Closed</span>
        </div>
      </div>

      {dealsWithCoords.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-[500]">
          <div className="bg-white bg-opacity-90 rounded-lg p-4 text-sm text-gray-500 text-center">
            <p>No geocoded deals to show.</p>
            <p className="text-xs mt-1">Deals will appear here after geocoding.</p>
          </div>
        </div>
      )}
    </div>
  )
}
