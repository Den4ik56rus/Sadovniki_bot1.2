// Billing Tab - Client payments, subscription & token management
import { useState, useEffect } from 'react'
import type { CrmClientFull, Payment, PaymentsResponse, SubscriptionPlan } from '@/types'
import { api } from '@/services/api'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './BillingTab.module.css'

interface BillingTabProps {
  client: CrmClientFull
  onUpdate: () => void
}

export function BillingTab({ client, onUpdate }: BillingTabProps) {
  const [paymentsData, setPaymentsData] = useState<PaymentsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [plans, setPlans] = useState<SubscriptionPlan[]>([])

  // Subscription form state
  const [planId, setPlanId] = useState<number | ''>(client.subscription_plan_id ?? '')
  const [startedAt, setStartedAt] = useState(toDatetimeLocal(client.subscription_started_at))
  const [expiresAt, setExpiresAt] = useState(toDatetimeLocal(client.subscription_expires_at))
  const [savingSubscription, setSavingSubscription] = useState(false)

  // Discount form state
  const [discountPercent, setDiscountPercent] = useState<number | ''>(client.personal_discount_percent ?? '')
  const [discountUntil, setDiscountUntil] = useState(toDatetimeLocal(client.personal_discount_valid_until))
  const [savingDiscount, setSavingDiscount] = useState(false)

  // Token balance form state
  const [subTokens, setSubTokens] = useState<number | ''>(client.subscription_token_balance ?? '')
  const [purTokens, setPurTokens] = useState<number | ''>(client.purchased_token_balance ?? '')
  const [savingTokens, setSavingTokens] = useState(false)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [paymentsRes, plansRes] = await Promise.all([
          api.getUserPayments(client.id, { limit: 50 }),
          api.getSubscriptionPlans(),
        ])
        setPaymentsData(paymentsRes)
        setPlans(plansRes.plans.filter(p => p.is_active))
      } catch (e) {
        console.error('Failed to fetch billing data:', e)
      } finally {
        setIsLoading(false)
      }
    }
    fetchData()
  }, [client.id])

  // Sync form when client data changes
  useEffect(() => {
    setPlanId(client.subscription_plan_id ?? '')
    setStartedAt(toDatetimeLocal(client.subscription_started_at))
    setExpiresAt(toDatetimeLocal(client.subscription_expires_at))
    setDiscountPercent(client.personal_discount_percent ?? '')
    setDiscountUntil(toDatetimeLocal(client.personal_discount_valid_until))
    setSubTokens(client.subscription_token_balance ?? '')
    setPurTokens(client.purchased_token_balance ?? '')
  }, [client])

  const handleSaveSubscription = async () => {
    setSavingSubscription(true)
    try {
      await api.updateClientBilling(client.id, {
        subscription_plan_id: planId !== '' ? Number(planId) : null,
        subscription_started_at: startedAt ? toISOString(startedAt) : null,
        subscription_expires_at: expiresAt ? toISOString(expiresAt) : null,
      })
      onUpdate()
    } catch (e) {
      console.error('Failed to save subscription:', e)
    } finally {
      setSavingSubscription(false)
    }
  }

  const handleSaveDiscount = async () => {
    setSavingDiscount(true)
    try {
      await api.updateClientBilling(client.id, {
        personal_discount_percent: discountPercent !== '' ? Number(discountPercent) : 0,
        personal_discount_valid_until: discountUntil ? toISOString(discountUntil) : null,
      })
      onUpdate()
    } catch (e) {
      console.error('Failed to save discount:', e)
    } finally {
      setSavingDiscount(false)
    }
  }

  const handleSaveTokens = async () => {
    setSavingTokens(true)
    try {
      await api.updateClientBilling(client.id, {
        subscription_token_balance: subTokens !== '' ? Number(subTokens) : 0,
        purchased_token_balance: purTokens !== '' ? Number(purTokens) : 0,
      })
      onUpdate()
    } catch (e) {
      console.error('Failed to save tokens:', e)
    } finally {
      setSavingTokens(false)
    }
  }

  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return '-'
    try {
      return format(new Date(dateStr), 'd MMM yyyy', { locale: ru })
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
          <span className={styles.summaryValue}>{client.total_consultations}</span>
          <span className={styles.summaryLabel}>Консультаций</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryValue}>{totalPaid.toFixed(0)} ₽</span>
          <span className={styles.summaryLabel}>Оплачено</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryValue}>{pendingAmount.toFixed(0)} ₽</span>
          <span className={styles.summaryLabel}>Ожидает</span>
        </div>
      </div>

      {/* Subscription Section */}
      <div className={styles.editSection}>
        <div className={styles.editSectionHeader}>
          <h4 className={styles.sectionTitle}>Тариф / Подписка</h4>
          {client.subscription_status && (
            <span className={`${styles.subStatusBadge} ${client.subscription_status === 'active' ? styles.active : styles.inactive}`}>
              {client.subscription_status === 'active' ? 'Активна' : client.subscription_status}
            </span>
          )}
        </div>

        <div className={styles.fieldGroup}>
          <label className={styles.fieldLabel}>Тарифный план</label>
          <select
            className={styles.select}
            value={planId}
            onChange={e => setPlanId(e.target.value !== '' ? Number(e.target.value) : '')}
          >
            <option value="">— нет подписки —</option>
            {plans.map(p => (
              <option key={p.id} value={p.id}>{p.name} ({p.tokens_included} токенов/мес)</option>
            ))}
          </select>
        </div>

        <div className={styles.fieldRow}>
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>Дата начала</label>
            <input
              type="datetime-local"
              className={styles.input}
              value={startedAt}
              onChange={e => setStartedAt(e.target.value)}
            />
          </div>
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>Дата окончания</label>
            <input
              type="datetime-local"
              className={styles.input}
              value={expiresAt}
              onChange={e => setExpiresAt(e.target.value)}
            />
          </div>
        </div>

        {client.subscription_expires_at && (
          <p className={styles.hint}>
            Текущий период: {formatDate(client.subscription_started_at)} — {formatDate(client.subscription_expires_at)}
          </p>
        )}

        <button
          className={styles.saveBtn}
          onClick={handleSaveSubscription}
          disabled={savingSubscription}
        >
          {savingSubscription ? 'Сохранение...' : 'Сохранить тариф'}
        </button>
      </div>

      {/* Personal Discount Section */}
      <div className={styles.editSection}>
        <h4 className={styles.sectionTitle}>Персональная скидка</h4>

        <div className={styles.fieldRow}>
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>Скидка %</label>
            <input
              type="number"
              className={styles.input}
              min={0}
              max={100}
              placeholder="0"
              value={discountPercent}
              onChange={e => setDiscountPercent(e.target.value !== '' ? Number(e.target.value) : '')}
            />
          </div>
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>Действует до</label>
            <input
              type="datetime-local"
              className={styles.input}
              value={discountUntil}
              onChange={e => setDiscountUntil(e.target.value)}
            />
          </div>
        </div>

        <button
          className={styles.saveBtn}
          onClick={handleSaveDiscount}
          disabled={savingDiscount}
        >
          {savingDiscount ? 'Сохранение...' : 'Сохранить скидку'}
        </button>
      </div>

      {/* Token Balances Section */}
      <div className={styles.editSection}>
        <h4 className={styles.sectionTitle}>Баланс токенов</h4>

        <div className={styles.fieldRow}>
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>Подписочные 🔄</label>
            <input
              type="number"
              className={styles.input}
              min={0}
              placeholder="0"
              value={subTokens}
              onChange={e => setSubTokens(e.target.value !== '' ? Number(e.target.value) : '')}
            />
          </div>
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>Купленные 🪙</label>
            <input
              type="number"
              className={styles.input}
              min={0}
              placeholder="0"
              value={purTokens}
              onChange={e => setPurTokens(e.target.value !== '' ? Number(e.target.value) : '')}
            />
          </div>
        </div>

        <p className={styles.hint}>
          Итого: {(Number(subTokens) || 0) + (Number(purTokens) || 0)} токенов
        </p>

        <button
          className={styles.saveBtn}
          onClick={handleSaveTokens}
          disabled={savingTokens}
        >
          {savingTokens ? 'Сохранение...' : 'Сохранить баланс'}
        </button>
      </div>

      {/* Payment History */}
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

// Helpers
function toDatetimeLocal(iso: string | null | undefined): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    // Format: YYYY-MM-DDTHH:mm
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch {
    return ''
  }
}

function toISOString(datetimeLocal: string): string {
  return new Date(datetimeLocal).toISOString()
}
