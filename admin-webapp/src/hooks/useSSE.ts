import { useEffect, useRef, useState, useCallback } from 'react'

interface UseSSEOptions {
  endpoint: string
  onMessage: (event: MessageEvent) => void
  onError?: (error: Event) => void
  enabled?: boolean
  reconnectInterval?: number
  maxReconnectAttempts?: number
  lastEventId?: string | null
}

interface UseSSEReturn {
  isConnected: boolean
  error: string | null
  reconnect: () => void
  close: () => void
}

/**
 * Универсальный хук для работы с SSE (Server-Sent Events).
 *
 * Особенности:
 * - Автоматический reconnect при обрыве связи
 * - Поддержка last_event_id для восстановления пропущенных событий
 * - Graceful cleanup при размонтировании компонента
 *
 * @example
 * ```tsx
 * const { isConnected, error } = useSSE({
 *   endpoint: '/api/admin/events/live-feed',
 *   onMessage: (event) => {
 *     const data = JSON.parse(event.data)
 *     console.log('New event:', data)
 *   }
 * })
 * ```
 */
export function useSSE({
  endpoint,
  onMessage,
  onError,
  enabled = true,
  reconnectInterval = 3000,
  maxReconnectAttempts = 5,
  lastEventId: _lastEventId
}: UseSSEOptions): UseSSEReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)

  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const isMountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!enabled) return

    // endpoint уже содержит last_event_id если нужно (формируется в api.ts)
    try {
      const eventSource = new EventSource(endpoint)
      eventSourceRef.current = eventSource

      eventSource.onopen = () => {
        console.log('[SSE] Connected:', endpoint)
        setIsConnected(true)
        setError(null)
        setReconnectAttempts(0)
      }

      // Обработка дефолтных message событий
      eventSource.onmessage = onMessage

      // Обработка кастомных типов событий (new_log, new_message, heartbeat и т.д.)
      // SSE спецификация требует addEventListener для кастомных типов
      const messageHandler = onMessage as EventListener
      eventSource.addEventListener('new_log', messageHandler)
      eventSource.addEventListener('new_message', messageHandler)
      eventSource.addEventListener('heartbeat', messageHandler)
      eventSource.addEventListener('status_update', messageHandler)

      eventSource.onerror = (event) => {
        console.error('[SSE] Error:', event)
        setIsConnected(false)

        if (onError) onError(event)

        // Auto-reconnect с экспоненциальным backoff
        if (reconnectAttempts < maxReconnectAttempts) {
          setError(`Переподключение... (${reconnectAttempts + 1}/${maxReconnectAttempts})`)

          reconnectTimeoutRef.current = setTimeout(() => {
            if (isMountedRef.current) {
              setReconnectAttempts(prev => prev + 1)
              eventSource.close()
              connect()
            }
          }, reconnectInterval)
        } else {
          setError('Не удалось подключиться. Обновите страницу.')
        }
      }
    } catch (err) {
      console.error('[SSE] Connection error:', err)
      setError(String(err))
      setIsConnected(false)
    }
  }, [endpoint, enabled, onMessage, onError, reconnectAttempts, reconnectInterval, maxReconnectAttempts])

  const close = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    setIsConnected(false)
  }, [])

  const reconnect = useCallback(() => {
    close()
    setReconnectAttempts(0)
    setError(null)
    connect()
  }, [close, connect])

  useEffect(() => {
    connect()
    return () => {
      isMountedRef.current = false
      close()
    }
  }, [connect, close])

  return { isConnected, error, reconnect, close }
}
