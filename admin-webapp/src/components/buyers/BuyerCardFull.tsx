// Buyer Card Full Modal (simplified version based on ClientCardFull)
import { useEffect, useState } from 'react'
import type { Buyer } from '@/types'
import { api } from '@/services/api'
import { useCurrencyStore } from '@/store'
import styles from '../crm/ClientCardFull.module.css'

interface BuyerCardFullProps {
  buyerId: number
  onClose: () => void
}

export function BuyerCardFull({ buyerId, onClose }: BuyerCardFullProps) {
  const [buyer, setBuyer] = useState<Buyer | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { usdRate } = useCurrencyStore()

  // Fetch buyer data
  useEffect(() => {
    async function loadBuyer() {
      setIsLoading(true)
      setError(null)
      try {
        const data = await api.getBuyer(buyerId)
        setBuyer(data)
      } catch (err) {
        setError(String(err))
      } finally {
        setIsLoading(false)
      }
    }
    loadBuyer()
  }, [buyerId])

  // Close on escape
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [onClose])

  // Handle backdrop click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  if (isLoading) {
    return (
      <div className={styles.backdrop} onClick={handleBackdropClick}>
        <div className={styles.modal}>
          <div className={styles.loading}>Загрузка...</div>
        </div>
      </div>
    )
  }

  if (error || !buyer) {
    return (
      <div className={styles.backdrop} onClick={handleBackdropClick}>
        <div className={styles.modal}>
          <div className={styles.error}>Ошибка: {error || 'Покупатель не найден'}</div>
        </div>
      </div>
    )
  }

  const displayName = buyer.first_name || buyer.username || `User ${buyer.telegram_user_id}`
  const costRub = buyer.total_cost_usd * usdRate

  // Format date
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    })
  }

  return (
    <div className={styles.backdrop} onClick={handleBackdropClick}>
      <div className={styles.modal}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <div className={styles.avatar}>
              {displayName.charAt(0).toUpperCase()}
            </div>
            <div className={styles.headerInfo}>
              <h2 className={styles.name}>{displayName}</h2>
              <span className={styles.subtitle}>
                @{buyer.username || '-'} • ID: {buyer.telegram_user_id}
              </span>
            </div>
          </div>
          <button className={styles.closeButton} onClick={onClose}>
            ✕
          </button>
        </div>

        {/* Content */}
        <div className={styles.content}>
          {/* Main Info */}
          <div className={styles.infoSection}>
            <h3 className={styles.sectionTitle}>Информация о покупателе</h3>
            <div className={styles.infoGrid}>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Статус</span>
                <span className={styles.infoValue}>{buyer.status}</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Дата покупки</span>
                <span className={styles.infoValue}>{formatDate(buyer.buyer_created_at)}</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Консультаций</span>
                <span className={styles.infoValue}>{buyer.total_consultations}</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Потрачено</span>
                <span className={styles.infoValue}>{costRub.toFixed(0)} ₽</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Токенов</span>
                <span className={styles.infoValue}>{buyer.total_tokens.toLocaleString()}</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Баланс</span>
                <span className={styles.infoValue}>{buyer.token_balance ?? 0} токенов</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Регион</span>
                <span className={styles.infoValue}>{buyer.region || '-'}</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Последняя активность</span>
                <span className={styles.infoValue}>{formatDate(buyer.last_consultation_at)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
