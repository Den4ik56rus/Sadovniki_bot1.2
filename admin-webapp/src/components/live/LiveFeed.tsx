import { useEffect, useCallback } from 'react'
import { useLiveFeedStore, useUIStore, useCurrencyStore } from '@/store'
import { useSSE } from '@/hooks/useSSE'
import { useScrollPreservation } from '@/hooks/useScrollPreservation'
import { api } from '@/services/api'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './LiveFeed.module.css'

export function LiveFeed() {
  const {
    logs,
    lastId,
    isLoading,
    error,
    fetchRecentLogs,
    addNewLog,
    setSseConnected,
  } = useLiveFeedStore()
  const { isLiveFeedPaused } = useUIStore()
  const { usdRate, fetchRate } = useCurrencyStore()

  const { containerRef, handleScroll } = useScrollPreservation({
    enabled: !isLiveFeedPaused,
    autoScrollThreshold: 100,
  })

  // Initial fetch
  useEffect(() => {
    fetchRecentLogs()
    fetchRate()
  }, [fetchRecentLogs, fetchRate])

  const toRub = (usd: number) => (usd * usdRate).toFixed(2)

  // SSE connection
  const handleSSEMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)

        // Игнорируем heartbeat
        if (event.type === 'heartbeat') return

        // Обрабатываем new_log события
        if (event.type === 'new_log') {
          // Нормализуем данные - добавляем дефолтные значения
          const normalizedLog = {
            ...data,
            user: data.user || { username: null, first_name: null, telegram_user_id: null },
            culture: data.culture || null,
            cost_usd: data.cost_usd || 0,
            latency_ms: data.latency_ms || 0,
          }
          addNewLog(normalizedLog)
        }
      } catch (error) {
        console.error('[LiveFeed] Failed to parse SSE event:', error, event)
      }
    },
    [addNewLog]
  )

  const { isConnected, error: sseError } = useSSE({
    endpoint: api.sse.liveFeed(),
    onMessage: handleSSEMessage,
    enabled: !isLiveFeedPaused,
    lastEventId: lastId?.toString(),
  })

  useEffect(() => {
    setSseConnected(isConnected)
  }, [isConnected, setSseConnected])

  if (error) {
    return <div className={styles.error}>Ошибка: {error}</div>
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2>Live Feed</h2>
        <div className={styles.controls}>
          {/* SSE Connection Indicator */}
          <span
            className={`${styles.indicator} ${
              isConnected ? styles.connected : styles.disconnected
            }`}
            title={isConnected ? 'Подключено к SSE' : 'Отключено от SSE'}
          >
            {isConnected ? '🟢 Подключено' : '🔴 Отключено'}
          </span>

          {sseError && (
            <span className={styles.errorText} title={sseError}>
              {sseError}
            </span>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className={styles.loading}>Загрузка...</div>
      ) : logs.length === 0 ? (
        <div className={styles.empty}>Нет консультаций</div>
      ) : (
        <div className={styles.feed} ref={containerRef} onScroll={handleScroll}>
          {logs.map((log) => (
            <div key={log.id} className={styles.logCard}>
              <div className={styles.logHeader}>
                <div className={styles.userInfo}>
                  <span className={styles.userName}>
                    {log.user.first_name || log.user.username || `User #${log.user.telegram_user_id}`}
                  </span>
                  {log.culture && (
                    <span className={styles.culture}>{log.culture}</span>
                  )}
                </div>
                <div className={styles.logMeta}>
                  <span className={styles.tokens}>{log.total_tokens.toLocaleString()} токенов</span>
                  <span className={styles.cost} title={`$${log.cost_usd.toFixed(4)}`}>
                    {toRub(log.cost_usd)} ₽
                  </span>
                  <span className={styles.latency}>{log.latency_ms}ms</span>
                </div>
              </div>

              <div className={styles.question}>
                <span className={styles.label}>Q:</span>
                <span className={styles.text}>{log.user_message}</span>
              </div>

              <div className={styles.answer}>
                <span className={styles.label}>A:</span>
                <span className={styles.text}>
                  {log.bot_response.length > 200
                    ? log.bot_response.substring(0, 200) + '...'
                    : log.bot_response}
                </span>
              </div>

              {log.created_at && (
                <div className={styles.timestamp}>
                  {format(new Date(log.created_at), 'd MMM, HH:mm:ss', { locale: ru })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
