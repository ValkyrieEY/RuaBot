import { useEffect, useRef, useState } from 'react'

export interface WebSocketMessage {
  type: 'message' | 'notice' | 'request'
  id: string
  timestamp: string
  time: string
  event_type: string
  post_type: string
  message_id?: string
  message_type?: string
  user_id?: string
  group_id?: string | null
  target_id?: string | null // For bot-sent messages, indicates the recipient
  raw_message?: string
  message?: string
  sender?: any
  is_self?: boolean
  is_system?: boolean
  notice_type?: string
  sub_type?: string
  operator_id?: string | null
  request_type?: string
  comment?: string
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void
  onConnected?: () => void
  onDisconnected?: () => void
  reconnectDelay?: number
  maxReconnectAttempts?: number
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    onMessage,
    onConnected,
    onDisconnected,
    reconnectDelay = 3000,
    maxReconnectAttempts = 10
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const shouldConnectRef = useRef(true)

  const connect = () => {
    if (!shouldConnectRef.current) return

    try {
      // Get WebSocket URL from current location
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const wsUrl = `${protocol}//${host}/ws/messages`

      console.log('[WebSocket] Connecting to:', wsUrl)
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('[WebSocket] Connected')
        setIsConnected(true)
        reconnectAttemptsRef.current = 0
        onConnected?.()

        // Send ping every 30 seconds to keep connection alive
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping')
          } else {
            clearInterval(pingInterval)
          }
        }, 30000)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('[WebSocket] Received message:', data)
          onMessage?.(data)
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error)
        }
      }

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error)
      }

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected')
        setIsConnected(false)
        wsRef.current = null
        onDisconnected?.()

        // Attempt to reconnect
        if (
          shouldConnectRef.current &&
          reconnectAttemptsRef.current < maxReconnectAttempts
        ) {
          reconnectAttemptsRef.current++
          console.log(
            `[WebSocket] Reconnecting in ${reconnectDelay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`
          )
          reconnectTimeoutRef.current = setTimeout(connect, reconnectDelay)
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.error('[WebSocket] Max reconnect attempts reached')
        }
      }

      wsRef.current = ws
    } catch (error) {
      console.error('[WebSocket] Connection failed:', error)
    }
  }

  const disconnect = () => {
    shouldConnectRef.current = false
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }

  useEffect(() => {
    shouldConnectRef.current = true
    connect()

    return () => {
      disconnect()
    }
  }, [])

  return {
    isConnected,
    disconnect,
    reconnect: () => {
      disconnect()
      shouldConnectRef.current = true
      connect()
    }
  }
}

