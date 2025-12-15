// Client Card for Kanban Board
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { CrmClient } from '@/types'
import { useCurrencyStore } from '@/store'
import styles from './ClientCard.module.css'

interface ClientCardProps {
  client: CrmClient
  onClick: () => void
}

export function ClientCard({ client, onClick }: ClientCardProps) {
  const { usdRate } = useCurrencyStore()

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: client.id,
    data: {
      type: 'client',
      client,
    },
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  // Format cost in rubles
  const costRub = client.total_cost_usd * usdRate
  const formatCost = (cost: number) => {
    if (cost < 1) {
      return `${Math.round(cost * 100)} коп.`
    }
    return `${cost.toFixed(0)} ₽`
  }

  // Get display name
  const displayName = client.first_name || client.username || `User ${client.telegram_user_id}`

  // Get subscription info (placeholder for now)
  const subscriptionInfo = 'Бесплатный'

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={styles.card}
      onClick={onClick}
    >
      <div className={styles.header}>
        <div className={styles.avatar}>
          {displayName.charAt(0).toUpperCase()}
        </div>
        <div className={styles.name}>
          <span className={styles.displayName}>{displayName}</span>
          {client.username && (
            <span className={styles.username}>@{client.username}</span>
          )}
        </div>
      </div>

      <div className={styles.metrics}>
        <div className={styles.metric}>
          <span className={styles.metricLabel}>Оплатил:</span>
          <span className={styles.metricValue}>0 ₽</span>
        </div>
        <div className={styles.metric}>
          <span className={styles.metricLabel}>Потрачено:</span>
          <span className={styles.metricValue}>{formatCost(costRub)}</span>
        </div>
      </div>

      <div className={styles.subscription}>
        <span className={styles.subscriptionBadge}>{subscriptionInfo}</span>
        {client.total_consultations > 0 && (
          <span className={styles.consultations}>
            {client.total_consultations} конс.
          </span>
        )}
      </div>
    </div>
  )
}
