// Buyer Card for Kanban Board (based on ClientCard)
import { useState } from 'react'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { Buyer } from '@/types'
import { useCurrencyStore } from '@/store'
import styles from '../crm/ClientCard.module.css'

const API_BASE = import.meta.env.VITE_API_URL || '/api/admin'

interface BuyerCardProps {
  buyer: Buyer
  onClick: () => void
}

// Helper to calculate days since last activity
function getDaysSince(dateStr: string | null): number {
  if (!dateStr) return 0
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  return Math.floor(diff / (1000 * 60 * 60 * 24))
}

// Format date as DD.MM.YYYY
function formatDate(dateStr: string | null): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

export function BuyerCard({ buyer, onClick }: BuyerCardProps) {
  const { usdRate } = useCurrencyStore()
  const [imgError, setImgError] = useState(false)

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: buyer.id,
    data: {
      type: 'buyer',
      buyer,
    },
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  // Format cost in rubles
  const costRub = buyer.total_cost_usd * usdRate
  const formatCost = (cost: number) => {
    if (cost < 1) return '0 ₽'
    return `${cost.toFixed(0)} ₽`
  }

  // Get display name
  const displayName = buyer.first_name || buyer.username || `User ${buyer.telegram_user_id}`

  // Days since last activity
  const daysSinceActivity = getDaysSince(buyer.last_consultation_at)

  // Source from CRM data (fallback to Telegram if not set)
  const source = buyer.source || 'Telegram'

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={styles.card}
      onClick={onClick}
    >
      {/* Header: Avatar + Name + Date */}
      <div className={styles.header}>
        <div className={styles.avatarSection}>
          {buyer.avatar_url && !imgError ? (
            <img
              src={`${API_BASE}${buyer.avatar_url.replace('/api/admin', '')}`}
              alt={displayName}
              className={styles.avatarImg}
              onError={() => setImgError(true)}
            />
          ) : (
            <div className={styles.avatar}>
              {displayName.charAt(0).toUpperCase()}
            </div>
          )}
          <div className={styles.info}>
            <span className={styles.source}>от: {source}</span>
            <span className={styles.name}>{displayName}</span>
          </div>
        </div>
        <span className={styles.date}>{formatDate(buyer.buyer_created_at || buyer.user_created_at)}</span>
      </div>

      {/* Comment placeholder */}
      {buyer.total_consultations > 0 && (
        <div className={styles.comment}>
          <span className={styles.commentIcon}>💬</span>
          <span className={styles.commentText}>
            {buyer.total_consultations} консультаций
          </span>
        </div>
      )}

      {/* Footer: Cost + Days + Button */}
      <div className={styles.footer}>
        <div className={styles.footerLeft}>
          {costRub > 0 && (
            <span className={styles.cost}>{formatCost(costRub)}</span>
          )}
          {daysSinceActivity > 0 && (
            <span className={styles.days}>{daysSinceActivity}дн •</span>
          )}
        </div>
        <button
          className={styles.actionButton}
          onClick={(e) => {
            e.stopPropagation()
            onClick()
          }}
        >
          Открыть
        </button>
      </div>
    </div>
  )
}
