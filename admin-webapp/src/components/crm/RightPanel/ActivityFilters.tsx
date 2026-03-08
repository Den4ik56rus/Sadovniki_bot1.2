// Activity Filters Component
import type { ActivityEventType } from '@/types'
import styles from './ActivityFilters.module.css'

interface ActivityFiltersProps {
  activeFilters: ActivityEventType[]
  allFilters: ActivityEventType[]
  onChange: (filters: ActivityEventType[]) => void
}

const _FILTER_LABELS: Record<ActivityEventType, { label: string; icon: string }> = {
  chat_message: { label: 'Сообщения', icon: '💬' },
  consultation: { label: 'Консультации', icon: '🧠' },
  article: { label: 'Статьи', icon: '📄' },
  task_created: { label: 'Задачи', icon: '✅' },
  task_completed: { label: 'Задачи', icon: '✅' },
  note: { label: 'Заметки', icon: '📝' },
  status_change: { label: 'Статус', icon: '🔄' },
  tag_change: { label: 'Теги', icon: '🏷️' },
  field_change: { label: 'Поля', icon: '✏️' },
  payment: { label: 'Платежи', icon: '💳' },
  payment_link_sent: { label: 'Ссылки на оплату', icon: '💳' },
  broadcast_sent: { label: 'Рассылки', icon: '📢' },
  broadcast_button_click: { label: 'Ответы', icon: '👆' },
  broadcast_poll_answer: { label: 'Опросы', icon: '📊' },
}
void _FILTER_LABELS // Available for future use

// Group task_created and task_completed into one filter
const VISIBLE_FILTERS: { type: ActivityEventType | 'tasks'; label: string; icon: string; includes: ActivityEventType[] }[] = [
  { type: 'chat_message', label: 'Чат', icon: '💬', includes: ['chat_message'] },
  { type: 'consultation', label: 'Консультации', icon: '🧠', includes: ['consultation'] },
  { type: 'tasks', label: 'Задачи', icon: '✅', includes: ['task_created', 'task_completed'] },
  { type: 'note', label: 'Заметки', icon: '📝', includes: ['note'] },
  { type: 'status_change', label: 'Изменения', icon: '🔄', includes: ['status_change', 'tag_change'] },
]

export function ActivityFilters({ activeFilters, allFilters, onChange }: ActivityFiltersProps) {
  const isFilterActive = (includes: ActivityEventType[]) => {
    return includes.every(t => activeFilters.includes(t))
  }

  const toggleFilter = (includes: ActivityEventType[]) => {
    const isActive = isFilterActive(includes)

    if (isActive) {
      // Remove these types
      onChange(activeFilters.filter(f => !includes.includes(f)))
    } else {
      // Add these types
      const newFilters = [...activeFilters]
      includes.forEach(t => {
        if (!newFilters.includes(t)) {
          newFilters.push(t)
        }
      })
      onChange(newFilters)
    }
  }

  const toggleAll = () => {
    if (activeFilters.length === allFilters.length) {
      onChange([])
    } else {
      onChange([...allFilters])
    }
  }

  return (
    <div className={styles.filters}>
      <button
        className={`${styles.filter} ${activeFilters.length === allFilters.length ? styles.active : ''}`}
        onClick={toggleAll}
      >
        Все
      </button>

      {VISIBLE_FILTERS.map(filter => (
        <button
          key={filter.type}
          className={`${styles.filter} ${isFilterActive(filter.includes) ? styles.active : ''}`}
          onClick={() => toggleFilter(filter.includes)}
          title={filter.label}
        >
          <span className={styles.icon}>{filter.icon}</span>
          <span className={styles.label}>{filter.label}</span>
        </button>
      ))}
    </div>
  )
}
