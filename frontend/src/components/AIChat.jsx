import { useState, useRef, useEffect } from 'react'
import { useParams, useLocation } from 'react-router-dom'
import { aiApi } from '../api/ai'
import { MessageCircle, X, Send, Trash2, Loader } from 'lucide-react'

export default function AIChat() {
  const [open, setOpen] = useState(false)
  const [history, setHistory] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const location = useLocation()

  // Try to detect deal ID from URL
  const dealMatch = location.pathname.match(/\/deals\/([^/]+)/)
  const dealId = dealMatch ? dealMatch[1] : null

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const userMessage = { role: 'user', content: input.trim() }
    setHistory(h => [...h, userMessage])
    setInput('')
    setLoading(true)

    try {
      let response
      if (!dealId) {
        // Dashboard: use AI search
        response = await aiApi.search(userMessage.content)
        const reply = response.data.interpretation
          ? `${response.data.interpretation}\n\n${response.data.results?.length ? `Found ${response.data.results.length} matching deals.` : 'No matching deals found.'}`
          : response.data.explanation || 'No results found.'
        setHistory(h => [...h, { role: 'assistant', content: reply }])
      } else {
        // Deal detail: contextual chat
        response = await aiApi.chat(userMessage.content, dealId, history)
        setHistory(h => [...h, { role: 'assistant', content: response.data.reply }])
      }
    } catch (err) {
      setHistory(h => [...h, { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <>
      {/* Toggle button */}
      <button
        onClick={() => setOpen(!open)}
        className="fixed bottom-6 right-6 w-12 h-12 bg-blue-600 text-white rounded-full shadow-lg flex items-center justify-center hover:bg-blue-700 z-50 transition-transform hover:scale-105"
      >
        {open ? <X className="h-5 w-5" /> : <MessageCircle className="h-5 w-5" />}
      </button>

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-20 right-6 w-96 bg-white rounded-xl shadow-2xl border border-gray-200 flex flex-col z-50" style={{ height: '480px' }}>
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-blue-600 text-white rounded-t-xl">
            <div>
              <p className="font-semibold text-sm">AI Assistant</p>
              <p className="text-xs text-blue-100">{dealId ? 'Deal context active' : 'Search mode'}</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setHistory([])}
                className="p-1 hover:bg-blue-500 rounded"
                title="Clear chat"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {history.length === 0 && (
              <div className="text-center text-gray-400 text-sm py-8">
                <MessageCircle className="h-8 w-8 mx-auto mb-2 opacity-40" />
                <p>{dealId ? 'Ask me about this deal...' : 'Search for deals or ask questions...'}</p>
              </div>
            )}
            {history.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-lg px-3 py-2">
                  <Loader className="h-4 w-4 text-gray-500 animate-spin" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="flex items-center gap-2 px-3 py-3 border-t border-gray-200">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message..."
              rows={1}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm resize-none focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              className="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </>
  )
}
