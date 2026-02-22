// Broadcast List — список всех рассылок

import { useBroadcastStore } from '@/store/broadcastStore'
import type { Broadcast, BroadcastStatus } from '@/types'
import styles from './BroadcastList.module.css'

const STATUS_LABELS: Record<BroadcastStatus, string> = {
  draft: 'Черновик',
  scheduled: 'Запланирована',
  sending: 'Отправляется',
  completed: 'Завершена',
  failed: 'Ошибка',
  cancelled: 'Отменена',
}

const TARGET_LABELS: Record<string, string> = {
  all: 'Все',
  invite_link: 'Инвайт-ссылка',
  funnel_stage: 'Воронка',
  manual: 'Вручную',
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

interface Props {
  onSelected: () => void
}

export function BroadcastList({ onSelected }: Props) {
  const {
    broadcasts,
    currentBroadcast,
    selectedIds,
    isLoading,
    selectBroadcast,
    toggleSelect,
  } = useBroadcastStore()

  const handleSelect = (broadcast: Broadcast) => {
    selectBroadcast(broadcast)
    onSelected()
  }

  const handleCheckbox = (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    toggleSelect(id)
  }

  if (isLoading) {
    return <div className={styles.loading}>Загрузка...</div>
  }

  if (broadcasts.length === 0) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyIcon}>📨</div>
        <div className={styles.emptyText}>Нет рассылок</div>
        <div className={styles.emptyHint}>Создайте первую рассылку для ваших пользователей</div>
      </div>
    )
  }

  return (
    <div className={styles.list}>
      {broadcasts.map((b) => (
        <div
          key={b.id}
          className={`${styles.card} ${currentBroadcast?.id === b.id ? styles.cardActive : ''} ${selectedIds.has(b.id) ? styles.cardSelected : ''}`}
          onClick={() => handleSelect(b)}
        >
          <div className={styles.cardHeader}>
            <div className={styles.cardHeaderLeft}>
              <div
                className={`${styles.checkbox} ${selectedIds.has(b.id) ? styles.checkboxChecked : ''}`}
                onClick={(e) => handleCheckbox(e, b.id)}
              >
                {selectedIds.has(b.id) && (
                  <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                    <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                )}
              </div>
              <span className={styles.title}>{b.title || 'Без названия'}</span>
            </div>
            <span className={`${styles.badge} ${styles[`badge_${b.status}`]}`}>
              {STATUS_LABELS[b.status]}
            </span>
          </div>

          <div className={styles.cardMeta}>
            <span className={styles.metaItem}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M6 1C3.24 1 1 3.24 1 6C1 8.76 3.24 11 6 11C8.76 11 11 8.76 11 6C11 3.24 8.76 1 6 1Z" stroke="currentColor" strokeWidth="1.2"/>
                <path d="M6 3V6L8 7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
              </svg>
              {formatDate(b.created_at)}
            </span>
            <span className={styles.metaItem}>
              {TARGET_LABELS[b.target_type] || b.target_type}
            </span>
          </div>

          <div className={styles.cardStats}>
            <div className={styles.stat}>
              <span className={styles.statValue}>{b.total_recipients}</span>
              <span className={styles.statLabel}>получателей</span>
            </div>
            {(b.status === 'sending' || b.status === 'completed' || b.status === 'failed') && (
              <>
                <div className={`${styles.stat} ${styles.statSent}`}>
                  <span className={styles.statValue}>{b.sent_count}</span>
                  <span className={styles.statLabel}>отправлено</span>
                </div>
                {b.failed_count > 0 && (
                  <div className={`${styles.stat} ${styles.statFailed}`}>
                    <span className={styles.statValue}>{b.failed_count}</span>
                    <span className={styles.statLabel}>ошибок</span>
                  </div>
                )}
              </>
            )}
          </div>

          {b.status === 'sending' && b.total_recipients > 0 && (
            <div className={styles.progressBar}>
              <div
                className={styles.progressFill}
                style={{
                  width: `${Math.round(((b.sent_count + b.failed_count) / b.total_recipients) * 100)}%`,
                }}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
