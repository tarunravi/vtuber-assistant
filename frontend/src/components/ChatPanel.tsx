import { useEffect, useMemo, useRef, useState } from 'react'
import { appEvents } from '../events'

type StreamMessage =
  | { type: 'start' }
  | { type: 'chunk'; data: string }
  | { type: 'end' }
  | { type: 'error'; message: string }
  | { type: 'emotion'; emotion: string }

type ConversationItem = {
  role: 'user' | 'assistant'
  content: string
}

export default function ChatPanel() {
  const [wsUrl, setWsUrl] = useState<string>('')
  const [connecting, setConnecting] = useState<boolean>(false)
  const wsRef = useRef<WebSocket | null>(null)
  const [input, setInput] = useState<string>('')
  const [messages, setMessages] = useState<ConversationItem[]>([])
  const [streaming, setStreaming] = useState<boolean>(false)
  const pendingAssistantRef = useRef<string>('')
  const transcriptEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const res = await fetch('/app-config.json')
        const cfg = await res.json()
        // Use environment variables for Docker compatibility
        const backendHost = import.meta.env.VITE_BACKEND_HOST || '127.0.0.1'
        const backendPort = import.meta.env.VITE_BACKEND_PORT || '8000'
        const defaultUrl = `ws://${backendHost}:${backendPort}/ws`
        const url = cfg?.llm?.backendWsUrl || defaultUrl
        if (!cancelled) setWsUrl(url)
      } catch {
        // Use environment variables for Docker compatibility
        const backendHost = import.meta.env.VITE_BACKEND_HOST || '127.0.0.1'
        const backendPort = import.meta.env.VITE_BACKEND_PORT || '8000'
        const defaultUrl = `ws://${backendHost}:${backendPort}/ws`
        if (!cancelled) setWsUrl(defaultUrl)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!wsUrl) return
    setConnecting(true)
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
    ws.onopen = () => setConnecting(false)
    ws.onerror = () => setConnecting(false)
    ws.onclose = () => { setConnecting(false); wsRef.current = null }
    ws.onmessage = (evt) => {
      try {
        const msg: StreamMessage = JSON.parse(evt.data)
        if (msg.type === 'start') {
          setStreaming(true)
          pendingAssistantRef.current = ''
          setMessages((prev) => [...prev, { role: 'assistant', content: '' }])
          return
        }
        if (msg.type === 'emotion') {
          // Broadcast emotion to Live2D component
          if (msg.emotion && typeof msg.emotion === 'string') {
            appEvents.dispatchEvent(new CustomEvent('emotion', { detail: { label: msg.emotion } }))
          }
          return
        }
        if (msg.type === 'chunk') {
          pendingAssistantRef.current += msg.data
          setMessages((prev) => {
            const next = prev.slice()
            for (let i = next.length - 1; i >= 0; i--) {
              if (next[i].role === 'assistant') {
                next[i] = { role: 'assistant', content: pendingAssistantRef.current }
                break
              }
            }
            return next
          })
          return
        }
        if (msg.type === 'end') {
          setStreaming(false)
          return
        }
        if (msg.type === 'error') {
          setStreaming(false)
          setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${msg.message}` }])
        }
      } catch {}
    }
    return () => { ws.close() }
  }, [wsUrl])

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const canSend = useMemo(() => {
    return !!wsRef.current && wsRef.current.readyState === WebSocket.OPEN && !streaming && input.trim().length > 0
  }, [input, streaming])

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || !wsRef.current) return
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    wsRef.current.send(JSON.stringify({ prompt: text }))
    setInput('')
  }

  return (
    <div
      style={{
        position: 'fixed',
        right: 12,
        bottom: 12,
        width: 360,
        maxHeight: '60vh',
        background: 'rgba(0,0,0,0.55)',
        color: '#fff',
        borderRadius: 10,
        padding: 10,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        zIndex: 20,
        backdropFilter: 'blur(4px)'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontWeight: 600 }}>Chat</div>
        <div style={{ fontSize: 12, opacity: 0.8 }}>
          {connecting ? 'Connecting…' : (streaming ? 'Streaming…' : 'Idle')}
        </div>
      </div>
      <div
        style={{
          overflowY: 'auto',
          flex: 1,
          minHeight: 140,
          maxHeight: '44vh',
          padding: 6,
          border: '1px solid rgba(255,255,255,0.2)',
          borderRadius: 8,
          background: 'rgba(0,0,0,0.3)'
        }}
      >
        {messages.length === 0 ? (
          <div style={{ opacity: 0.7, fontSize: 13 }}>Ask the model anything…</div>
        ) : (
          messages.map((m, idx) => (
            <div key={idx} style={{ margin: '6px 0', whiteSpace: 'pre-wrap' }}>
              <span style={{ fontWeight: 600, color: m.role === 'user' ? '#8fd3ff' : '#b8ffa5' }}>
                {m.role === 'user' ? 'You' : 'Assistant'}:
              </span>
              <span style={{ marginLeft: 6 }}>{m.content}</span>
            </div>
          ))
        )}
        <div ref={transcriptEndRef} />
      </div>
      <form onSubmit={onSubmit} style={{ display: 'flex', gap: 6 }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          style={{
            flex: 1,
            padding: '8px 10px',
            borderRadius: 8,
            border: '1px solid rgba(255,255,255,0.25)',
            background: '#111',
            color: '#fff'
          }}
        />
        <button
          type="submit"
          disabled={!canSend}
          style={{
            padding: '8px 12px',
            borderRadius: 8,
            border: '1px solid rgba(255,255,255,0.25)',
            background: canSend ? '#2b87ff' : '#333',
            color: '#fff',
            cursor: canSend ? 'pointer' : 'not-allowed'
          }}
        >
          Send
        </button>
      </form>
    </div>
  )
}


