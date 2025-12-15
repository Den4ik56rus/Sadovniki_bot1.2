// Billing Tab - Client consultations & costs
import { useState, useEffect } from 'react'
import type { Topic } from '@/types'
import { api } from '@/services/api'
import { useCurrencyStore } from '@/store'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './BillingTab.module.css'

interface BillingTabProps {
  clientId: number
  totalCostUsd: number
  totalConsultations: number
  onTopicClick?: (topicId: number) => void
}

export function BillingTab({
  clientId,
  totalCostUsd,
  totalConsultations,
  onTopicClick,
}: BillingTabProps) {
  const { usdRate } = useCurrencyStore()
  const [topics, setTopics] = useState<Topic[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchTopics = async () => {
      try {
        const data = await api.getClientTopics(clientId, { limit: 50 })
        setTopics(data)
      } catch (e) {
        console.error('Failed to fetch topics:', e)
      } finally {
        setIsLoading(false)
      }
    }
    fetchTopics()
  }, [clientId])

  const formatCost = (costUsd: number) => {
    const costRub = costUsd * usdRate
    if (costRub < 1) {
      return `${Math.round(costRub * 100)} коп.`
    }
    return `${costRub.toFixed(0)} ₽`
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    try {
      return format(new Date(dateStr), 'd MMM yyyy, HH:mm', { locale: ru })
    } catch {
      return '-'
    }
  }

  const totalCostRub = totalCostUsd * usdRate

  return (
    <div className={styles.content}>
      {/* Summary */}
      <div className={styles.summary}>
        <div className={styles.summaryItem}>
          <span className={styles.summaryValue}>{totalConsultations}</span>
          <span className={styles.summaryLabel}>Всего консультаций</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryValue}>{totalCostRub.toFixed(0)} ₽</span>
          <span className={styles.summaryLabel}>Общие расходы</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryValue}>0 ₽</span>
          <span className={styles.summaryLabel}>Оплачено клиентом</span>
        </div>
      </div>

      {/* Consultations list */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>История консультаций</h4>

        {isLoading ? (
          <div className={styles.loading}>Загрузка...</div>
        ) : topics.length === 0 ? (
          <p className={styles.empty}>Нет консультаций</p>
        ) : (
          <div className={styles.topicsList}>
            {topics.map((topic) => (
              <div
                key={topic.id}
                className={styles.topicItem}
                onClick={() => onTopicClick?.(topic.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && onTopicClick?.(topic.id)}
              >
                <div className={styles.topicHeader}>
                  <span className={styles.topicCategory}>
                    {topic.category || 'Консультация'}
                  </span>
                  {topic.culture && (
                    <span className={styles.topicCulture}>{topic.culture}</span>
                  )}
                  <span className={`${styles.topicStatus} ${styles[topic.status]}`}>
                    {topic.status === 'open' ? 'Активен' : 'Закрыт'}
                  </span>
                </div>

                <div className={styles.topicMeta}>
                  <span className={styles.topicDate}>
                    {formatDate(topic.created_at)}
                  </span>
                  <span className={styles.topicMessages}>
                    {topic.message_count} сообщ.
                  </span>
                  <span className={styles.topicCost}>
                    {formatCost(topic.total_cost_usd)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
