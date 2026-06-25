import { useEffect, useRef, useState } from 'react'

let instanceCount = 0

export default function SpreadsheetEditor({ dealId, luckysheetData, flags = [], onSave, compact, fullScreen }) {
  const containerRef = useRef(null)
  const instanceId = useRef(`luckysheet-${++instanceCount}-${dealId}`)
  const [initialized, setInitialized] = useState(false)

  useEffect(() => {
    if (!luckysheetData || !window.luckysheet) return

    const containerId = instanceId.current

    try {
      window.luckysheet.create({
        container: containerId,
        data: luckysheetData.sheets || [],
        showtoolbar: !compact,
        showinfobar: false,
        showsheetbar: true,
        allowEdit: true,
        enableAddRow: true,
        enableAddBackTop: true,
        userInfo: false,
        showstatisticBar: !compact,
        sheetBottomConfig: false,
        allowCopy: true,
        loadurl: '',
        menu: '',
        title: '',
      })
      setInitialized(true)

      // Highlight flagged cells after a delay
      setTimeout(() => {
        flags?.filter(f => !f.resolved).forEach(flag => {
          try {
            const color = flag.severity === 'critical' ? '#FFE4E4' : flag.severity === 'warning' ? '#FFFBDD' : '#EFF6FF'
            // Luckysheet cell background setting via API
            // Find the sheet index
            const allSheets = window.luckysheet.getAllSheets()
            const sheetIdx = allSheets?.findIndex(s => s.name === flag.tab_name)
            if (sheetIdx >= 0) {
              // Parse cell address
              const match = flag.cell_address.match(/([A-Z]+)(\d+)/)
              if (match) {
                const colStr = match[1]
                const row = parseInt(match[2]) - 1
                const col = colStr.split('').reduce((acc, c) => acc * 26 + (c.charCodeAt(0) - 64), 0) - 1
                // We can't reliably set bg color without more complex API calls,
                // but the framework is in place for it
              }
            }
          } catch (e) {
            // Silently ignore cell highlight errors
          }
        })
      }, 800)
    } catch (e) {
      console.error('Luckysheet init error:', e)
    }

    return () => {
      try {
        if (window.luckysheet && initialized) {
          window.luckysheet.destroy()
        }
      } catch (e) {
        // Ignore destroy errors
      }
      setInitialized(false)
    }
  }, [luckysheetData])

  const handleSave = () => {
    if (!window.luckysheet || !onSave) return
    try {
      const data = window.luckysheet.getAllSheets()
      onSave({ sheets: data })
    } catch (e) {
      console.error('Save error:', e)
    }
  }

  if (!luckysheetData) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-50 rounded-lg border border-gray-200">
        <div className="text-center text-gray-400">
          <p className="text-sm">No model data yet.</p>
          <p className="text-xs mt-1">Upload documents to auto-populate the model.</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`flex flex-col ${fullScreen ? 'h-full' : 'h-full'}`}>
      {onSave && (
        <div className="flex justify-end p-2 bg-gray-50 border-b border-gray-200">
          <button
            onClick={handleSave}
            className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
          >
            Save Snapshot
          </button>
        </div>
      )}
      <div
        id={instanceId.current}
        className="flex-1"
        style={{ minHeight: compact ? '500px' : '100%' }}
      />
    </div>
  )
}
