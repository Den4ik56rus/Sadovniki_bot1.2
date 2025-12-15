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
}

export function ActivityItem({
  event,
  onTaskComplete,
  onTaskDelete,
  onNoteDelete,
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
      default:
        return '📌'
    }
  }

  const renderContent = () => {
    const data = event.event_data

    switch (event.event_type) {
      case 'consultation':
        return (
          <div className={styles.consultation}>
            <div className={styles.consultationHeader}>
              <span className={styles.consultationCategory}>
                {(data.category as string) || 'Консультация'}
              </span>
              {data.culture && (
                <span className={styles.consultationCulture}>
                  {data.culture as string}
                </span>
              )}
            </div>
            {data.first_question && (
              <div className={styles.consultationQuestion}>
                {data.first_question as string}
                {(data.first_question as string).length >= 150 && '...'}
              </div>
            )}
            <div className={styles.consultationMeta}>
              <span>{data.message_count} сообщ.</span>
              <span className={styles.consultationCost}>
                {formatCost((data.total_cost_usd as number) || 0)}
              </span>
            </div>
          </div>
        )

      case 'task_created':
        return (
          <div className={styles.task}>
            <div className={styles.taskTitle}>{data.title as string}</div>
            {data.due_date && (
              <div className={styles.taskDue}>
                📅 {formatDate(data.due_date as string)}
              </div>
            )}
            {data.priority && data.priority !== 'medium' && (
              <span className={`${styles.priority} ${styles[data.priority as string]}`}>
                {data.priority === 'high' ? '🔴 Высокий' : '🔵 Низкий'}
              </span>
            )}
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
