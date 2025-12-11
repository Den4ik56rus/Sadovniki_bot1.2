import { useEffect, useCallback } from 'react'
import { useTopicsStore, useUIStore, useCurrencyStore } from '@/store'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import { useSSE } from '@/hooks/useSSE'
import { api } from '@/services/api'
import styles from './TopicTimeline.module.css'

export function TopicTimeline() {
  const { topics, isLoading, error, fetchTopics, clearTopics } = useTopicsStore()
  const { selectedUserId, selectedTopicId, selectTopic } = useUIStore()
  const { usdRate, fetchRate } = useCurrencyStore()

  // SSE handler для автоматического обновления топиков при новых консультациях
  const handleSSEMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)

        // Игнорируем heartbeat
        if (event.type === 'heartbeat') return

        // При новом логе для выбранного пользователя - обновляем топики
        if (event.type === 'new_log' && selectedUserId && data.user_id === selectedUserId) {
          console.log('[TopicTimeline] SSE event: new_log for user', selectedUserId)
          fetchTopics(selectedUserId)
        }
      } catch (error) {
        console.error('[TopicTimeline] Failed to parse SSE:', error)
      }
    },
    [selectedUserId, fetchTopics]
  )

  // Подключаемся к SSE только когда пользователь выбран
  useSSE({
    endpoint: api.sse.liveFeed(),
    onMessage: handleSSEMessage,
    enabled: !!selectedUserId,
  })

  useEffect(() => {
    if (selectedUserId) {
      fetchTopics(selectedUserId)
      fetchRate()
    } else {
      clearTopics()
    }
  }, [selectedUserId, fetchTopics, clearTopics, fetchRate])

  const toRub = (usd: number) => (usd * usdRate).toFixed(2)

  if (!selectedUserId) {
    return (
      <div className={styles.empty}>
        Выберите пользователя для просмотра топиков
      </div>
    )
  }

  if (isLoading) {
    return <div className={styles.loading}>Загрузка...</div>
  }

  if (error) {
    return <div className={styles.error}>Ошибка: {error}</div>
  }

  if (topics.length === 0) {
    return <div className={styles.empty}>Нет топиков</div>
  }

  return (
    <div className={styles.container}>
      <h3 className={styles.title}>Топики</h3>
      <div className={styles.timeline}>
        {topics.map((topic) => (
          <div
            key={topic.id}
            className={`${styles.topicCard} ${selectedTopicId === topic.id ? styles.selected : ''}`}
            onClick={() => selectTopic(topic.id)}
          >
            <div className={styles.topicHeader}>
              <span
                className={`${styles.status} ${topic.status === 'open' ? styles.statusOpen : styles.statusClosed}`}
              >
                {topic.status === 'open' ? 'Открыт' : 'Закрыт'}
              </span>
              <span className={styles.date}>
                {topic.created_at &&
                  format(new Date(topic.created_at), 'd MMM yyyy, HH:mm', {
                    locale: ru,
                  })}
              </span>
            </div>
            <div className={styles.topicMeta}>
              {topic.culture && (
                <span className={styles.culture}>{topic.culture}</span>
              )}
              {topic.category && (
                <span className={styles.category}>{topic.category}</span>
              )}
            </div>
            <div className={styles.topicStats}>
              <span>{topic.message_count} сообщ.</span>
              <span>{topic.total_tokens.toLocaleString()} токенов</span>
              <span className={styles.cost} title={`$${topic.total_cost_usd.toFixed(4)}`}>
                {toRub(topic.total_cost_usd)} ₽
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
