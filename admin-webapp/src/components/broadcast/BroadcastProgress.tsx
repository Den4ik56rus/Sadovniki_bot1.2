// Broadcast Progress — прогресс отправки рассылки

import { useEffect, useRef } from 'react'
import { useBroadcastStore } from '@/store/broadcastStore'
import type { Broadcast } from '@/types'
import styles from './BroadcastDetail.module.css'

interface Props {
  broadcast: Broadcast
}

export function BroadcastProgress({ broadcast }: Props) {
  const { refreshBroadcast, cancelBroadcast } = useBroadcastStore()
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Poll for updates every 3 seconds while sending
  useEffect(() => {
    if (broadcast.status === 'sending') {
      intervalRef.current = setInterval(() => {
        refreshBroadcast(broadcast.id)
      }, 3000)
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [broadcast.id, broadcast.status, refreshBroadcast])

  const total = broadcast.total_recipients || 1
  const processed = broadcast.sent_count + broadcast.failed_count
  const percent = Math.round((processed / total) * 100)
  const remaining = total - processed

  const handleCancel = async () => {
    if (!confirm('Отменить рассылку? Уже отправленные сообщения не будут отозваны.')) return
    await cancelBroadcast(broadcast.id)
  }

  return (
    <div className={styles.progressSection}>
      <div className={styles.progressHeader}>
        <span className={styles.progressTitle}>Отправка рассылки</span>
        <span className={styles.progressPercent}>{percent}%</span>
      </div>

      <div className={styles.progressBarLarge}>
        <div
          className={styles.progressBarFill}
          style={{ width: `${percent}%` }}
        />
      </div>

      <div className={styles.progressStats}>
        <div className={styles.progressStat}>
          <span className={styles.progressStatValue} style={{ color: '#15803D' }}>
            {broadcast.sent_count}
          </span>
          <span className={styles.progressStatLabel}>отправлено</span>
        </div>
        <div className={styles.progressStat}>
          <span className={styles.progressStatValue} style={{ color: '#B91C1C' }}>
            {broadcast.failed_count}
          </span>
          <span className={styles.progressStatLabel}>ошибок</span>
        </div>
        <div className={styles.progressStat}>
          <span className={styles.progressStatValue} style={{ color: '#6B7280' }}>
            {remaining}
          </span>
          <span className={styles.progressStatLabel}>осталось</span>
        </div>
      </div>

      <button className={styles.cancelSendBtn} onClick={handleCancel}>
        Отменить отправку
      </button>
    </div>
  )
}
