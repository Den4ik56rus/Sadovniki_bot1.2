// Payments List - All user payments display
import { useState, useEffect } from 'react'
import type { Payment, PaymentStats, PaymentStatus, PaymentType } from '@/types'
import { api } from '@/services/api'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './PaymentsList.module.css'

export function PaymentsList() {
  const [payments, setPayments] = useState<Payment[]>([])
  const [stats, setStats] = useState<PaymentStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<PaymentStatus | ''>('')
  const [typeFilter, setTypeFilter] = useState<PaymentType | ''>('')
  const [page, setPage] = useState(0)
  const limit = 50

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true)
        const [paymentsData, statsData] = await Promise.all([
          api.getAllPayments({
            limit,
            offset: page * limit,
            status: statusFilter || undefined,
            payment_type: typeFilter || undefined,
          }),
          api.getPaymentStats('all'),
        ])
        setPayments(paymentsData.payments)
        setStats(statsData)
      } catch (e) {
        console.error('Failed to fetch payments:', e)
      } finally {
        setIsLoading(false)
      }
    }
    fetchData()
  }, [page, statusFilter, typeFilter])

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    try {
      return format(new Date(dateStr), 'd MMM yyyy, HH:mm', { locale: ru })
    } catch {
      return '-'
    }
  }

  const getProductName = (payment: Payment): string => {
    if (payment.payment_type === 'subscription') {
      return payment.subscription_plan_name || 'Подписка'
    }
    return payment.token_package_name || 'Токены'
  }

  const getStatusLabel = (payment: Payment): string => {
    if (payment.paid) return 'Оплачено'
    if (payment.status === 'pending') return 'Ожидание'
    if (payment.status === 'canceled') return 'Отменено'
    return payment.status
  }

  const getStatusClass = (payment: Payment): string => {
    if (payment.paid) return 'succeeded'
    if (payment.status === 'pending') return 'pending'
    return 'canceled'
  }

  const getUserName = (payment: Payment): string => {
    if (payment.first_name) return payment.first_name
    if (payment.username) return `@${payment.username}`
    return `ID: ${payment.telegram_user_id}`
  }

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <h1 className={styles.title}>Платежи</h1>
        <button className={styles.refreshButton} onClick={() => setPage(0)}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M13 3L13 7L9 7M3 13L3 9L7 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M12.5 6.5C12 5.2 10.9 4.2 9.5 3.9C7.4 3.4 5.3 4.4 4.2 6.2M3.5 9.5C4 10.8 5.1 11.8 6.5 12.1C8.6 12.6 10.7 11.6 11.8 9.8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          Обновить
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className={styles.statsCards}>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{stats.paid_amount.toFixed(0)} ₽</div>
            <div className={styles.statLabel}>Всего получено</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{stats.pending_amount.toFixed(0)} ₽</div>
            <div className={styles.statLabel}>Ожидает оплаты</div>
          </div>
          <div className={styles.statCard}>
            <div className={styles.statValue}>{stats.total_count}</div>
            <div className={styles.statLabel}>Всего платежей</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className={styles.filters}>
        <select
          className={styles.filterSelect}
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as PaymentStatus | '')
            setPage(0)
          }}
        >
          <option value="">Все статусы</option>
          <option value="succeeded">Оплачено</option>
          <option value="pending">Ожидание</option>
          <option value="canceled">Отменено</option>
        </select>

        <select
          className={styles.filterSelect}
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value as PaymentType | '')
            setPage(0)
          }}
        >
          <option value="">Все типы</option>
          <option value="subscription">Подписки</option>
          <option value="tokens">Токены</option>
        </select>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className={styles.loading}>Загрузка...</div>
      ) : payments.length === 0 ? (
        <div className={styles.empty}>Нет платежей</div>
      ) : (
        <div className={styles.table}>
          <div className={styles.tableHeader}>
            <div>Дата</div>
            <div>Пользователь</div>
            <div>Продукт</div>
            <div>Сумма</div>
            <div>Статус</div>
            <div>Оплачено</div>
          </div>

          {payments.map((payment) => (
            <div key={payment.id} className={styles.tableRow}>
              <div className={styles.tableCell}>{formatDate(payment.created_at)}</div>
              <div className={styles.tableCell}>{getUserName(payment)}</div>
              <div className={styles.tableCell}>
                <span className={styles.productIcon}>
                  {payment.payment_type === 'subscription' ? '💳' : '🪙'}
                </span>
                {getProductName(payment)}
              </div>
              <div className={styles.tableCell}>
                <span className={styles.amount}>{payment.amount_rub.toFixed(0)} ₽</span>
              </div>
              <div className={styles.tableCell}>
                <span className={`${styles.statusBadge} ${styles[getStatusClass(payment)]}`}>
                  {getStatusLabel(payment)}
                </span>
              </div>
              <div className={styles.tableCell}>{formatDate(payment.paid_at)}</div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {payments.length > 0 && (
        <div className={styles.pagination}>
          <span className={styles.paginationInfo}>
            {page * limit + 1}–{page * limit + payments.length}
          </span>

          <div className={styles.paginationButtons}>
            <button
              className={styles.paginationButton}
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              ← Назад
            </button>
            <button
              className={styles.paginationButton}
              onClick={() => setPage(p => p + 1)}
              disabled={payments.length < limit}
            >
              Далее →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
