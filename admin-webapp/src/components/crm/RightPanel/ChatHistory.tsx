// ChatHistory - Full conversation timeline for a client
import { useState, useEffect, useRef, useMemo } from 'react'
import type { Message, ChatHistoryTopic } from '@/types'
import { api } from '@/services/api'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './ChatHistory.module.css'

interface ChatHistoryProps {
  clientId: number
  onTopicClick?: (topicId: number) => void
}

export function ChatHistory({ clientId, onTopicClick }: ChatHistoryProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [topics, setTopics] = useState<ChatHistoryTopic[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const fetch = async () => {
      setIsLoading(true)
      try {
        const data = await api.getClientChatHistory(clientId)
        setMessages(data.messages)
        setTopics(data.topics)
      } catch (e) {
        console.error('Failed to fetch chat history:', e)
      } finally {
        setIsLoading(false)
      }
    }
    fetch()
  }, [clientId])

  // Scroll to bottom after load
  useEffect(() => {
    if (!isLoading && messages.length > 0 && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [isLoading, messages.length])

  // Build topics map for quick lookup
  const topicsMap = useMemo(() => {
    const map = new Map<number, ChatHistoryTopic>()
    for (const t of topics) {
      map.set(t.id, t)
    }
    return map
  }, [topics])

  const formatTime = (dateStr: string | null) => {
    if (!dateStr) return ''
    try {
      return format(new Date(dateStr), 'HH:mm', { locale: ru })
    } catch {
      return ''
    }
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return ''
    try {
      return format(new Date(dateStr), 'd MMMM yyyy', { locale: ru })
    } catch {
      return ''
    }
  }

  // Build timeline with topic dividers and date separators
  const timeline = useMemo(() => {
    const items: Array<
      | { type: 'message'; data: Message }
      | { type: 'topic_start'; topicId: number; topic: ChatHistoryTopic }
      | { type: 'date'; date: string }
    > = []

    let currentTopicId: number | null | undefined = undefined
    let currentDate = ''

    for (const msg of messages) {
      // Date separator
      const msgDate = formatDate(msg.created_at)
      if (msgDate && msgDate !== currentDate) {
        currentDate = msgDate
        items.push({ type: 'date', date: msgDate })
      }

      // Topic divider when topic changes
      if (msg.topic_id !== currentTopicId && msg.topic_id != null) {
        const topic = topicsMap.get(msg.topic_id)
        if (topic) {
          items.push({ type: 'topic_start', topicId: msg.topic_id, topic })
        }
        currentTopicId = msg.topic_id
      } else if (msg.topic_id !== currentTopicId) {
        currentTopicId = msg.topic_id
      }

      items.push({ type: 'message', data: msg })
    }

    return items
  }, [messages, topicsMap])

  if (isLoading) {
    return <div className={styles.loading}>Загрузка...</div>
  }

  if (messages.length === 0) {
    return <div className={styles.empty}>Нет сообщений</div>
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.headerTitle}>Полный чат</span>
        <span className={styles.messageCount}>{messages.length} сообщений</span>
      </div>

      <div className={styles.messages} ref={listRef}>
        {timeline.map((item, idx) => {
          if (item.type === 'date') {
            return (
              <div key={`date-${idx}`} className={styles.dateSeparator}>
                <div className={styles.dateSeparatorLine} />
                <span>{item.date}</span>
                <div className={styles.dateSeparatorLine} />
              </div>
            )
          }

          if (item.type === 'topic_start') {
            const label = [
              item.topic.category,
              item.topic.culture,
            ].filter(Boolean).join(' / ') || `Консультация #${item.topicId}`

            return (
              <div
                key={`topic-${item.topicId}-${idx}`}
                className={styles.topicDivider}
                onClick={() => onTopicClick?.(item.topicId)}
                title="Открыть детальный просмотр консультации"
              >
                <div className={styles.topicDividerLine} />
                <span className={styles.topicDividerLabel}>
                  📋 {label}
                  <span className={styles.topicDividerArrow}>→</span>
                </span>
                <div className={styles.topicDividerLine} />
              </div>
            )
          }

          const msg = item.data
          const isUser = msg.direction === 'user'
          const isCallback = msg.meta?.type === 'callback'
          const hasKeyboard = msg.direction === 'bot' && msg.meta?.keyboard
          const isSystemBot = msg.direction === 'bot' && !msg.topic_id

          return (
            <div
              key={`msg-${msg.id}`}
              className={`${styles.messageBubble} ${
                isUser ? styles.userMessage :
                isSystemBot ? styles.systemMessage :
                styles.botMessage
              }`}
            >
              <div className={styles.messageContent}>
                {msg.text}
                {isCallback && (
                  <span className={styles.callbackBadge}>кнопка</span>
                )}
              </div>

              {/* Keyboard buttons */}
              {hasKeyboard && msg.meta?.keyboard && (
                <div className={styles.keyboardButtons}>
                  {msg.meta.keyboard.buttons.map((row, rowIdx) => (
                    <div key={rowIdx} className={styles.keyboardRow}>
                      {row.map((btn, btnIdx) => (
                        <span key={btnIdx} className={styles.keyboardButton}>
                          {btn.text}
                        </span>
                      ))}
                    </div>
                  ))}
                </div>
              )}

              {msg.created_at && (
                <div className={styles.messageTime}>
                  {formatTime(msg.created_at)}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
