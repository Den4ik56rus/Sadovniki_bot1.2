import { useEffect, useRef, useState, useCallback } from 'react'

const DEFAULT_EVENT_TYPES = ['new_log', 'new_message', 'heartbeat', 'status_update']

interface UseSSEOptions {
  endpoint: string
  onMessage: (event: MessageEvent) => void
  onError?: (error: Event) => void
  enabled?: boolean
  reconnectInterval?: number
  maxReconnectAttempts?: number
  lastEventId?: string | null
  eventTypes?: string[]
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
 * - Стабильное подключение — не переподключается при изменении callback-ов
 * - Graceful cleanup при размонтировании компонента
 */
export function useSSE({
  endpoint,
  onMessage,
  onError,
  enabled = true,
  reconnectInterval = 3000,
  maxReconnectAttempts = 5,
  lastEventId,
  eventTypes = DEFAULT_EVENT_TYPES,
}: UseSSEOptions): UseSSEReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Инкрементируется для принудительного reconnect через публичный метод
  const [connectKey, setConnectKey] = useState(0)

  // Refs для стабильности — изменения callback-ов и счётчиков не вызывают переподключение
  const onMessageRef = useRef(onMessage)
  const onErrorRef = useRef(onError)
  const reconnectAttemptsRef = useRef(0)
  const lastEventIdRef = useRef(lastEventId)
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const isMountedRef = useRef(true)

  // Обновляем refs при изменении props (без вызова переподключения)
  useEffect(() => { onMessageRef.current = onMessage }, [onMessage])
  useEffect(() => { onErrorRef.current = onError }, [onError])
  useEffect(() => { lastEventIdRef.current = lastEventId }, [lastEventId])

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
  }, [])

  // Основной эффект подключения — зависит только от endpoint, enabled и connectKey
  useEffect(() => {
    isMountedRef.current = true

    if (!enabled) {
      cleanup()
      setIsConnected(false)
      return
    }

    const connect = () => {
      // Закрываем предыдущее соединение если есть
      cleanup()

      // Формируем URL с last_event_id при reconnect
      let url = endpoint
      const currentLastEventId = lastEventIdRef.current
      if (currentLastEventId && reconnectAttemptsRef.current > 0) {
        const separator = url.includes('?') ? '&' : '?'
        url = `${url}${separator}last_event_id=${currentLastEventId}`
      }

      try {
        const eventSource = new EventSource(url)
        eventSourceRef.current = eventSource

        eventSource.onopen = () => {
          if (!isMountedRef.current) return
          console.log('[SSE] Connected:', endpoint)
          setIsConnected(true)
          setError(null)
          reconnectAttemptsRef.current = 0
        }

        // Handler через ref — не вызывает переподключение при изменении
        const messageHandler = (event: MessageEvent) => {
          onMessageRef.current(event)
        }

        eventSource.onmessage = messageHandler

        // SSE спецификация: addEventListener для кастомных event types
        for (const eventType of eventTypes) {
          eventSource.addEventListener(eventType, messageHandler as EventListener)
        }

        eventSource.onerror = (event) => {
          if (!isMountedRef.current) return
          console.error('[SSE] Error:', event)
          setIsConnected(false)

          if (onErrorRef.current) onErrorRef.current(event)

          // Закрываем сломанное соединение
          eventSource.close()
          eventSourceRef.current = null

          // Auto-reconnect с backoff
          if (reconnectAttemptsRef.current < maxReconnectAttempts) {
            reconnectAttemptsRef.current += 1
            const attempt = reconnectAttemptsRef.current
            const delay = reconnectInterval * Math.min(attempt, 3)

            setError(`Переподключение... (${attempt}/${maxReconnectAttempts})`)

            reconnectTimeoutRef.current = setTimeout(() => {
              if (isMountedRef.current) {
                connect()
              }
            }, delay)
          } else {
            setError('Не удалось подключиться. Обновите страницу.')
          }
        }
      } catch (err) {
        console.error('[SSE] Connection error:', err)
        setError(String(err))
        setIsConnected(false)
      }
    }

    connect()

    return () => {
      isMountedRef.current = false
      cleanup()
      setIsConnected(false)
      reconnectAttemptsRef.current = 0
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint, enabled, connectKey])

  const close = useCallback(() => {
    cleanup()
    setIsConnected(false)
  }, [cleanup])

  const reconnect = useCallback(() => {
    cleanup()
    reconnectAttemptsRef.current = 0
    setError(null)
    setConnectKey(k => k + 1)
  }, [cleanup])

  return { isConnected, error, reconnect, close }
}
