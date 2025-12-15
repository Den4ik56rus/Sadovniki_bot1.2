// Topic View - Shows conversation dialog
import { useState, useEffect, useRef } from 'react'
import type { TopicLogsResponse, Message } from '@/types'
import { api } from '@/services/api'
import { useCurrencyStore } from '@/store'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './TopicView.module.css'

interface TopicViewProps {
  topicId: number
  onBack: () => void
}

export function TopicView({ topicId, onBack }: TopicViewProps) {
  const { usdRate } = useCurrencyStore()
  const [data, setData] = useState<TopicLogsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const messagesRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const fetchTopic = async () => {
      try {
        const response = await api.getTopicLogs(topicId)
        setData(response)
      } catch (e) {
        console.error('Failed to fetch topic:', e)
      } finally {
        setIsLoading(false)
      }
    }
    fetchTopic()
  }, [topicId])

  // Scroll to bottom after messages load
  useEffect(() => {
    if (!isLoading && data && messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }
  }, [isLoading, data])

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    try {
      return format(new Date(dateStr), 'd MMM yyyy, HH:mm', { locale: ru })
    } catch {
      return '-'
    }
  }

  const formatCost = (costUsd: number) => {
    const costRub = costUsd * usdRate
    if (costRub < 1) {
      return `${Math.round(costRub * 100)} коп.`
    }
    return `${costRub.toFixed(0)} ₽`
  }

  if (isLoading) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <button className={styles.backBtn} onClick={onBack}>
            ← Назад к ленте
          </button>
        </div>
        <div className={styles.loading}>Загрузка...</div>
      </div>
    )
  }

  if (!data || !data.topic) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <button className={styles.backBtn} onClick={onBack}>
            ← Назад к ленте
          </button>
        </div>
        <div className={styles.empty}>Топик не найден</div>
      </div>
    )
  }

  const { topic, messages, logs } = data
  const totalCost = logs.reduce((sum, log) => sum + log.cost_usd, 0)
  // Get category from first log if available
  const category = logs[0]?.consultation_category || 'Консультация'

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <button className={styles.backBtn} onClick={onBack}>
          ← Назад к ленте
        </button>
        <div className={styles.topicInfo}>
          <span className={styles.topicCategory}>
            {category}
          </span>
          {topic.culture && (
            <span className={styles.topicCulture}>{topic.culture}</span>
          )}
          <span className={`${styles.topicStatus} ${styles[topic.status]}`}>
            {topic.status === 'open' ? 'Активен' : 'Закрыт'}
          </span>
        </div>
      </div>

      {/* Topic stats */}
      <div className={styles.stats}>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Начало</span>
          <span className={styles.statValue}>{formatDate(topic.created_at)}</span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Сообщений</span>
          <span className={styles.statValue}>{messages.length}</span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Расходы</span>
          <span className={styles.statValue}>{formatCost(totalCost)}</span>
        </div>
      </div>

      {/* Messages */}
      <div className={styles.messages} ref={messagesRef}>
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
      </div>
    </div>
  )
}

// Message bubble component
function MessageBubble({ message }: { message: Message }) {
  const isUser = message.direction === 'user'

  const formatTime = (dateStr: string | null) => {
    if (!dateStr) return ''
    try {
      return format(new Date(dateStr), 'HH:mm', { locale: ru })
    } catch {
      return ''
    }
  }

  return (
    <div className={`${styles.messageBubble} ${isUser ? styles.userMessage : styles.botMessage}`}>
      <div className={styles.messageContent}>
        {message.text}
      </div>
      <span className={styles.messageTime}>{formatTime(message.created_at)}</span>
    </div>
  )
}
