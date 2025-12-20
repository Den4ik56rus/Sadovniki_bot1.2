// Activity Item Component
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import type { ActivityEvent } from '@/types'
import { useCurrencyStore } from '@/store'
import styles from './ActivityItem.module.css'

interface ActivityItemProps {
  event: ActivityEvent
  onTaskComplete?: (taskId: number) => void
  onTaskDelete?: (taskId: number) => void
  onNoteDelete?: (noteId: number) => void
  onTopicClick?: (topicId: number) => void
  onArticleClick?: (articleId: number) => void
}

export function ActivityItem({
  event,
  onTaskComplete,
  onTaskDelete,
  onNoteDelete,
  onTopicClick,
  onArticleClick,
}: ActivityItemProps) {
  const { usdRate } = useCurrencyStore()

  const formatDate = (dateStr: string) => {
    try {
      return format(new Date(dateStr), 'd MMM, HH:mm', { locale: ru })
    } catch {
      return dateStr
    }
  }

  const formatCost = (costUsd: number) => {
    const costRub = costUsd * usdRate
    if (costRub < 1) {
      return `${Math.round(costRub * 100)} коп.`
    }
    return `${costRub.toFixed(0)} ₽`
  }

  const getEventIcon = () => {
    switch (event.event_type) {
      case 'consultation':
        return '💬'
      case 'task_created':
        return '📋'
      case 'task_completed':
        return '✅'
      case 'note':
        return '📝'
      case 'status_change':
        return '🔄'
      case 'tag_change':
        return '🏷️'
      case 'field_change':
        return '✏️'
      case 'article':
        return '📄'
      case 'payment':
        return '💰'
      default:
        return '📌'
    }
  }

  const handleConsultationClick = () => {
    const topicId = event.event_data.topic_id as number | undefined
    if (topicId && onTopicClick) {
      onTopicClick(topicId)
    }
  }

  const handleArticleClick = () => {
    const articleId = event.event_data.article_id as number | undefined
    if (articleId && onArticleClick) {
      onArticleClick(articleId)
    }
  }

  const renderContent = () => {
    const data = event.event_data

    switch (event.event_type) {
      case 'consultation':
        return (
          <div
            className={`${styles.consultation} ${onTopicClick ? styles.clickable : ''}`}
            onClick={handleConsultationClick}
            role={onTopicClick ? 'button' : undefined}
            tabIndex={onTopicClick ? 0 : undefined}
            onKeyDown={(e) => e.key === 'Enter' && handleConsultationClick()}
          >
            <div className={styles.consultationHeader}>
              <span className={styles.consultationCategory}>
                {(data.category as string) || 'Консультация'}
              </span>
              {data.culture ? (
                <span className={styles.consultationCulture}>
                  {String(data.culture)}
                </span>
              ) : null}
              {onTopicClick && (
                <span className={styles.clickHint}>→</span>
              )}
            </div>
            {data.first_question ? (
              <div className={styles.consultationQuestion}>
                {String(data.first_question)}
                {String(data.first_question).length >= 150 && '...'}
              </div>
            ) : null}
            <div className={styles.consultationMeta}>
              <span>{String(data.message_count)} сообщ.</span>
              <span className={styles.consultationCost}>
                {formatCost((data.total_cost_usd as number) || 0)}
              </span>
            </div>
          </div>
        )

      case 'task_created':
        return (
          <div className={styles.task}>
            <div className={styles.taskTitle}>{String(data.title)}</div>
            {data.due_date ? (
              <div className={styles.taskDue}>
                📅 {formatDate(data.due_date as string)}
              </div>
            ) : null}
            {data.priority && data.priority !== 'medium' ? (
              <span className={`${styles.priority} ${styles[String(data.priority)]}`}>
                {data.priority === 'high' ? '🔴 Высокий' : '🔵 Низкий'}
              </span>
            ) : null}
            <div className={styles.taskActions}>
              <button
                className={styles.completeBtn}
                onClick={() => onTaskComplete?.(data.task_id as number)}
              >
                Выполнить
              </button>
              <button
                className={styles.deleteBtn}
                onClick={() => onTaskDelete?.(data.task_id as number)}
              >
                Удалить
              </button>
            </div>
          </div>
        )

      case 'task_completed':
        return (
          <div className={styles.taskCompleted}>
            <span className={styles.strikethrough}>{data.title as string}</span>
            <span className={styles.completedLabel}>выполнено</span>
          </div>
        )

      case 'note':
        return (
          <div className={styles.note}>
            <div className={styles.noteText}>
              {data.text_preview as string}
            </div>
            <button
              className={styles.deleteBtn}
              onClick={() => onNoteDelete?.(data.note_id as number)}
            >
              Удалить
            </button>
          </div>
        )

      case 'status_change':
        return (
          <div className={styles.statusChange}>
            <span className={styles.oldStatus}>{getStatusLabel(data.old_status as string)}</span>
            <span className={styles.arrow}>→</span>
            <span className={styles.newStatus}>{getStatusLabel(data.new_status as string)}</span>
          </div>
        )

      case 'tag_change':
        return (
          <div className={styles.tagChange}>
            {data.action === 'added' ? (
              <span>Добавлен тег <strong>{data.tag_name as string}</strong></span>
            ) : (
              <span>Удалён тег <strong>{data.tag_name as string}</strong></span>
            )}
          </div>
        )

      case 'field_change':
        return (
          <div className={styles.fieldChange}>
            <span>Изменено поле <strong>{data.field_name as string}</strong></span>
          </div>
        )

      case 'article':
        return (
          <div
            className={`${styles.article} ${onArticleClick ? styles.clickable : ''}`}
            onClick={handleArticleClick}
            role={onArticleClick ? 'button' : undefined}
            tabIndex={onArticleClick ? 0 : undefined}
            onKeyDown={(e) => e.key === 'Enter' && handleArticleClick()}
          >
            <div className={styles.articleHeader}>
              <span className={styles.articleLabel}>Статья</span>
              {onArticleClick && (
                <span className={styles.clickHint}>→</span>
              )}
            </div>
            {data.topic ? (
              <div className={styles.articleTopic}>
                {String(data.topic)}
                {String(data.topic).length >= 100 && '...'}
              </div>
            ) : null}
            <div className={styles.articleMeta}>
              <span>{Number(data.article_length || 0).toLocaleString()} симв.</span>
              <span className={styles.articleCost}>
                {formatCost((data.cost_usd as number) || 0)}
              </span>
              {data.llm_model ? (
                <span className={styles.articleModel}>{String(data.llm_model)}</span>
              ) : null}
            </div>
          </div>
        )

      case 'payment': {
        const paymentData = data as {
          payment_id: number
          amount_rub: number
          payment_type: 'subscription' | 'tokens'
          paid: boolean
          product_name: string
          paid_at: string | null
        }

        return (
          <div className={styles.payment}>
            <div className={styles.paymentHeader}>
              <span className={styles.paymentType}>
                {paymentData.payment_type === 'subscription' ? 'Подписка' : 'Токены'}
              </span>
              <span className={paymentData.paid ? styles.paymentBadge : styles.paymentBadgePending}>
                {paymentData.paid ? '✓ Оплачено' : '⏳ Ожидание'}
              </span>
            </div>
            <div className={styles.paymentProduct}>{paymentData.product_name}</div>
            <div className={styles.paymentMeta}>
              <span className={styles.paymentAmount}>{paymentData.amount_rub.toFixed(0)} ₽</span>
              {paymentData.paid_at && (
                <span>{format(new Date(paymentData.paid_at), 'd MMM yyyy', { locale: ru })}</span>
              )}
            </div>
          </div>
        )
      }

      default:
        return <div>Неизвестное событие</div>
    }
  }

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      new: 'Новый',
      tried: 'Попробовал',
      trial_ended: 'Закончился триал',
      paid: 'Купил',
    }
    return labels[status] || status
  }

  return (
    <div className={styles.item}>
      <div className={styles.icon}>{getEventIcon()}</div>
      <div className={styles.content}>
        <div className={styles.body}>{renderContent()}</div>
        <div className={styles.time}>{formatDate(event.created_at)}</div>
      </div>
    </div>
  )
}
