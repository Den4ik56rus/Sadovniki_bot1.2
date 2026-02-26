// TriggerList — list of trigger cards with event type filter chips

import { useTriggerStore } from '@/store/triggerStore'
import type { AutomationTrigger, TriggerEventType } from '@/types'
import styles from './TriggerList.module.css'

const EVENT_LABELS: Record<TriggerEventType, string> = {
  stage_transition: 'Этап',
  payment_success: 'Оплата',
  tag_changed: 'Тег',
  subscription_expiring: 'Подписка',
}


function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

interface Props {
  onSelected: () => void
}

export function TriggerList({ onSelected }: Props) {
  const {
    triggers,
    currentTrigger,
    isLoading,
    filterEventType,
    setFilterEventType,
    setCurrentTrigger,
    toggleTrigger,
  } = useTriggerStore()

  const handleSelect = (trigger: AutomationTrigger) => {
    setCurrentTrigger(trigger)
    onSelected()
  }

  const eventTypes: (TriggerEventType | null)[] = [null, 'stage_transition', 'payment_success', 'tag_changed', 'subscription_expiring']

  if (isLoading) {
    return <div className={styles.loading}>Загрузка...</div>
  }

  if (triggers.length === 0 && !filterEventType) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyIcon}>&#9889;</div>
        <div className={styles.emptyText}>Нет триггеров</div>
        <div className={styles.emptyHint}>Создайте первый триггер автоматизации</div>
      </div>
    )
  }

  return (
    <div>
      {/* Filter chips */}
      <div className={styles.filters}>
        {eventTypes.map(type => (
          <button
            key={type || 'all'}
            className={`${styles.filterChip} ${filterEventType === type ? styles.filterChipActive : ''}`}
            onClick={() => setFilterEventType(type)}
          >
            {type === null ? 'Все' : EVENT_LABELS[type]}
          </button>
        ))}
      </div>

      {/* List */}
      {triggers.length === 0 ? (
        <div className={styles.empty}>
          <div className={styles.emptyText}>Нет триггеров с этим фильтром</div>
        </div>
      ) : (
        <div className={styles.list}>
          {triggers.map(trigger => (
            <div
              key={trigger.id}
              className={`${styles.card} ${currentTrigger?.id === trigger.id ? styles.cardActive : ''} ${!trigger.is_active ? styles.cardInactive : ''}`}
              onClick={() => handleSelect(trigger)}
            >
              <div className={styles.cardHeader}>
                <div className={styles.cardHeaderLeft}>
                  <span className={styles.title}>{trigger.name}</span>
                  <span className={`${styles.badge} ${styles[`badge_${trigger.event_type}`]}`}>
                    {EVENT_LABELS[trigger.event_type]}
                  </span>
                </div>
                <label className={styles.toggle} onClick={e => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    className={styles.toggleInput}
                    checked={trigger.is_active}
                    onChange={() => toggleTrigger(trigger.id, !trigger.is_active)}
                  />
                  <span className={styles.toggleSlider} />
                </label>
              </div>

              <div className={styles.cardMeta}>
                <span className={styles.metaItem}>
                  {trigger.actions.length} {trigger.actions.length === 1 ? 'действие' : 'действий'}
                </span>
                {trigger.delay_minutes > 0 && (
                  <span className={styles.metaItem}>
                    {trigger.delay_minutes < 60
                      ? `${trigger.delay_minutes} мин.`
                      : `${Math.floor(trigger.delay_minutes / 60)}ч ${trigger.delay_minutes % 60 > 0 ? `${trigger.delay_minutes % 60}м` : ''}`
                    }
                  </span>
                )}
                {trigger.conditions && trigger.conditions.groups.length > 0 && (
                  <span className={styles.metaItem}>
                    {trigger.conditions.groups.length} условие
                  </span>
                )}
                <span className={styles.metaItem}>
                  {formatDate(trigger.created_at)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
