// Billing Tab - Client payments & subscriptions
import { useState, useEffect } from 'react'
import type { Payment, PaymentsResponse } from '@/types'
import { api } from '@/services/api'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './BillingTab.module.css'

interface BillingTabProps {
  clientId: number
  totalConsultations: number
}

export function BillingTab({
  clientId,
  totalConsultations,
}: BillingTabProps) {
  const [paymentsData, setPaymentsData] = useState<PaymentsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchPayments = async () => {
      try {
        const data = await api.getUserPayments(clientId, { limit: 50 })
        setPaymentsData(data)
      } catch (e) {
        console.error('Failed to fetch payments:', e)
      } finally {
        setIsLoading(false)
      }
    }
    fetchPayments()
  }, [clientId])

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
    if (payment.paid) return 'paid'
    if (payment.status === 'pending') return 'pending'
    return 'canceled'
  }

  const totalPaid = paymentsData?.total_paid || 0
  const pendingAmount = paymentsData?.payments
    ?.filter(p => p.status === 'pending')
    .reduce((sum, p) => sum + p.amount_rub, 0) || 0

  return (
    <div className={styles.content}>
      {/* Summary */}
      <div className={styles.summary}>
        <div className={styles.summaryItem}>
          <span className={styles.summaryValue}>{totalConsultations}</span>
          <span className={styles.summaryLabel}>Всего консультаций</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryValue}>{totalPaid.toFixed(0)} ₽</span>
          <span className={styles.summaryLabel}>Оплачено клиентом</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryValue}>{pendingAmount.toFixed(0)} ₽</span>
          <span className={styles.summaryLabel}>Ожидает оплаты</span>
        </div>
      </div>

      {/* Payments list */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>История платежей</h4>

        {isLoading ? (
          <div className={styles.loading}>Загрузка...</div>
        ) : !paymentsData || paymentsData.payments.length === 0 ? (
          <p className={styles.empty}>Нет платежей</p>
        ) : (
          <div className={styles.paymentsList}>
            {paymentsData.payments.map((payment) => (
              <div key={payment.id} className={styles.paymentItem}>
                <div className={styles.paymentHeader}>
                  <span className={styles.paymentIcon}>
                    {payment.payment_type === 'subscription' ? '💳' : '🪙'}
                  </span>
                  <span className={styles.paymentProduct}>
                    {getProductName(payment)}
                  </span>
                  <span className={`${styles.paymentStatus} ${styles[getStatusClass(payment)]}`}>
                    {getStatusLabel(payment)}
                  </span>
                </div>

                <div className={styles.paymentMeta}>
                  <span className={styles.paymentAmount}>
                    {payment.amount_rub.toFixed(0)} ₽
                  </span>
                  <span className={styles.paymentDate}>
                    {formatDate(payment.paid_at || payment.created_at)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
