// Stage Trigger Editor — управление триггерами рассылок на этапе воронки

import { useState, useEffect } from 'react'
import { useFunnelStore } from '@/store/funnelStore'
import { api } from '@/services/api'
import type { Broadcast, FunnelStageTrigger, TriggerPaymentConfig } from '@/types'
import { BroadcastForm } from '@/components/broadcast/BroadcastForm'
import styles from './StageTriggerEditor.module.css'

interface SubscriptionPlan {
  id: number
  name: string
  price_rub: number
  tokens_included: number
  duration_days: number
  is_active: boolean
}

interface Props {
  funnelId: string
  stageKey: string
  triggers: FunnelStageTrigger[]
}

const DELAY_OPTIONS = [
  { label: 'Сразу', value: 0 },
  { label: '30 мин', value: 30 },
  { label: '1 час', value: 60 },
  { label: '3 часа', value: 180 },
  { label: '24 часа', value: 1440 },
  { label: '2 дня', value: 2880 },
  { label: '3 дня', value: 4320 },
  { label: '7 дней', value: 10080 },
]

function formatDelay(minutes: number): string {
  if (!minutes) return ''
  const opt = DELAY_OPTIONS.find((o) => o.value === minutes)
  if (opt) return opt.label
  if (minutes < 60) return `${minutes} мин`
  if (minutes < 1440) return `${Math.round(minutes / 60)} ч`
  return `${Math.round(minutes / 1440)} дн`
}

export function StageTriggerEditor({ funnelId, stageKey, triggers }: Props) {
  const { createTrigger, deleteTrigger, toggleTrigger } = useFunnelStore()
  const [broadcasts, setBroadcasts] = useState<Broadcast[]>([])
  const [plans, setPlans] = useState<SubscriptionPlan[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedBroadcastId, setSelectedBroadcastId] = useState<number | null>(null)
  const [delayMinutes, setDelayMinutes] = useState<number>(0)
  const [enablePayment, setEnablePayment] = useState(false)
  const [paymentPlanId, setPaymentPlanId] = useState<number | null>(null)
  const [customPrice, setCustomPrice] = useState<string>('')
  const [bonusTokens, setBonusTokens] = useState<string>('')
  const [isAdding, setIsAdding] = useState(false)
  const [showCreateBroadcast, setShowCreateBroadcast] = useState(false)

  // Load broadcasts and plans when opening add form
  useEffect(() => {
    if (!isAdding) return
    if (broadcasts.length === 0) {
      setLoading(true)
      api.getBroadcasts().then((data) => {
        setBroadcasts(data.broadcasts.filter((b) =>
          b.message_text || b.photo_path || b.poll_question
        ))
      }).catch(() => {}).finally(() => setLoading(false))
    }
    if (plans.length === 0) {
      api.getSubscriptionPlans().then((data) => {
        setPlans((data.plans as SubscriptionPlan[]).filter((p) => p.is_active))
      }).catch(() => {})
    }
  }, [isAdding, broadcasts.length, plans.length])

  const resetForm = () => {
    setSelectedBroadcastId(null)
    setDelayMinutes(0)
    setEnablePayment(false)
    setPaymentPlanId(null)
    setCustomPrice('')
    setBonusTokens('')
  }

  const handleAdd = async () => {
    if (!selectedBroadcastId) return

    const paymentConfig: TriggerPaymentConfig | null = enablePayment && paymentPlanId
      ? {
          plan_id: paymentPlanId,
          custom_price: customPrice ? Number(customPrice) : null,
          bonus_tokens: bonusTokens ? Number(bonusTokens) : null,
        }
      : null

    const ok = await createTrigger(funnelId, stageKey, selectedBroadcastId, delayMinutes, paymentConfig)
    if (ok) {
      setIsAdding(false)
      resetForm()
    }
  }

  const handleDelete = async (triggerId: number) => {
    if (!confirm('Удалить триггер?')) return
    await deleteTrigger(triggerId)
  }

  const handleToggle = async (trigger: FunnelStageTrigger) => {
    await toggleTrigger(trigger.id, !trigger.is_active)
  }

  const stageTriggers = triggers.filter((t) => t.stage_key === stageKey)
  const usedBroadcastIds = new Set(stageTriggers.map((t) => t.broadcast_id))

  return (
    <div className={styles.container}>
      {/* Existing triggers */}
      {stageTriggers.map((trigger) => (
        <div key={trigger.id} className={`${styles.triggerCard} ${!trigger.is_active ? styles.triggerCardDisabled : ''}`}>
          <div className={styles.triggerInfo}>
            <span className={styles.triggerIcon}>⚡</span>
            <div className={styles.triggerText}>
              <span className={styles.triggerTitle}>{trigger.broadcast_title}</span>
              <div className={styles.triggerMeta}>
                <span className={styles.triggerStatus}>
                  {trigger.is_active ? 'Активен' : 'Выключен'}
                </span>
                {!!trigger.delay_minutes && (
                  <span className={styles.badge}>⏱ {formatDelay(trigger.delay_minutes)}</span>
                )}
                {trigger.payment_config && (
                  <span className={`${styles.badge} ${styles.badgePayment}`}>
                    💳{trigger.payment_config.custom_price ? ` ${trigger.payment_config.custom_price}₽` : ''}
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className={styles.triggerActions}>
            <button
              className={`${styles.toggleBtn} ${trigger.is_active ? styles.toggleBtnActive : ''}`}
              onClick={() => handleToggle(trigger)}
              title={trigger.is_active ? 'Выключить' : 'Включить'}
            >
              <div className={styles.toggleTrack}>
                <div className={styles.toggleThumb} />
              </div>
            </button>
            <button
              className={styles.deleteTriggerBtn}
              onClick={() => handleDelete(trigger.id)}
              title="Удалить"
            >
              ✕
            </button>
          </div>
        </div>
      ))}

      {/* Add trigger form */}
      {isAdding ? (
        <div className={styles.addForm}>
          {loading ? (
            <div className={styles.loadingText}>Загрузка рассылок...</div>
          ) : (
            <>
              {/* Broadcast selector */}
              <select
                className={styles.selectBroadcast}
                value={selectedBroadcastId ?? ''}
                onChange={(e) => setSelectedBroadcastId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Выберите рассылку</option>
                {broadcasts
                  .filter((b) => !usedBroadcastIds.has(b.id))
                  .map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.title || `#${b.id}`}
                    </option>
                  ))}
              </select>

              <button
                type="button"
                className={styles.createBroadcastBtn}
                onClick={() => setShowCreateBroadcast(true)}
              >
                + Создать рассылку
              </button>

              {/* Delay selector */}
              <div className={styles.formRow}>
                <label className={styles.formLabel}>⏱ Задержка</label>
                <select
                  className={styles.selectDelay}
                  value={delayMinutes}
                  onChange={(e) => setDelayMinutes(Number(e.target.value))}
                >
                  {DELAY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              {/* Payment button toggle */}
              <label className={styles.checkboxRow}>
                <input
                  type="checkbox"
                  checked={enablePayment}
                  onChange={(e) => {
                    setEnablePayment(e.target.checked)
                    if (!e.target.checked) {
                      setPaymentPlanId(null)
                      setCustomPrice('')
                      setBonusTokens('')
                    }
                  }}
                />
                <span className={styles.formLabel}>💳 Добавить кнопку оплаты</span>
              </label>

              {/* Payment config */}
              {enablePayment && (
                <div className={styles.paymentConfig}>
                  <select
                    className={styles.selectBroadcast}
                    value={paymentPlanId ?? ''}
                    onChange={(e) => setPaymentPlanId(e.target.value ? Number(e.target.value) : null)}
                  >
                    <option value="">Выберите тариф</option>
                    {plans.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} — {p.price_rub}₽/мес, {p.tokens_included} токенов
                      </option>
                    ))}
                  </select>
                  <div className={styles.paymentFields}>
                    <div className={styles.paymentField}>
                      <label className={styles.fieldLabel}>Цена (₽)</label>
                      <input
                        type="number"
                        className={styles.fieldInput}
                        placeholder={
                          paymentPlanId
                            ? String(plans.find((p) => p.id === paymentPlanId)?.price_rub ?? '')
                            : 'по умолчанию'
                        }
                        value={customPrice}
                        onChange={(e) => setCustomPrice(e.target.value)}
                        min={1}
                      />
                    </div>
                    <div className={styles.paymentField}>
                      <label className={styles.fieldLabel}>Бонус токенов</label>
                      <input
                        type="number"
                        className={styles.fieldInput}
                        placeholder="0"
                        value={bonusTokens}
                        onChange={(e) => setBonusTokens(e.target.value)}
                        min={0}
                      />
                    </div>
                  </div>

                  {/* Preview */}
                  {paymentPlanId && (
                    <div className={styles.paymentPreview}>
                      {(() => {
                        const plan = plans.find((p) => p.id === paymentPlanId)
                        if (!plan) return null
                        const price = customPrice ? Number(customPrice) : plan.price_rub
                        const tokens = plan.tokens_included + (bonusTokens ? Number(bonusTokens) : 0)
                        const discount = customPrice && Number(customPrice) < plan.price_rub
                          ? Math.round((1 - Number(customPrice) / plan.price_rub) * 100)
                          : 0
                        return (
                          <div className={styles.previewText}>
                            <div>📅 Подписка: <b>{plan.name}</b></div>
                            {discount > 0
                              ? <div>💰 <s>{plan.price_rub}₽</s> → <b>{price}₽</b>/мес (скидка {discount}%)</div>
                              : <div>💰 <b>{price}₽</b>/мес</div>
                            }
                            <div>🎁 {tokens} токенов/мес{bonusTokens ? ` (+${bonusTokens} бонус)` : ''}</div>
                          </div>
                        )
                      })()}
                    </div>
                  )}
                </div>
              )}

              <div className={styles.addFormActions}>
                <button
                  className={styles.confirmAddBtn}
                  onClick={handleAdd}
                  disabled={!selectedBroadcastId || (enablePayment && !paymentPlanId)}
                >
                  Добавить
                </button>
                <button
                  className={styles.cancelAddBtn}
                  onClick={() => { setIsAdding(false); resetForm() }}
                >
                  Отмена
                </button>
              </div>
            </>
          )}
        </div>
      ) : (
        <button
          className={styles.addTriggerBtn}
          onClick={() => setIsAdding(true)}
        >
          + Добавить триггер
        </button>
      )}

      {/* Create broadcast modal */}
      {showCreateBroadcast && (
        <div className={styles.modalBackdrop} onClick={() => setShowCreateBroadcast(false)}>
          <div className={styles.modalPanel} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <span>Новая рассылка</span>
              <button
                className={styles.modalCloseBtn}
                onClick={() => setShowCreateBroadcast(false)}
              >
                ✕
              </button>
            </div>
            <div className={styles.modalBody}>
              <BroadcastForm
                broadcast={null}
                onSaved={async () => {
                  setShowCreateBroadcast(false)
                  // Перезагрузить список рассылок и авто-выбрать новую
                  const data = await api.getBroadcasts()
                  const all = data.broadcasts.filter((b: Broadcast) =>
                    b.message_text || b.photo_path || b.poll_question
                  )
                  setBroadcasts(all)
                  if (all.length > 0) {
                    const newest = all.reduce((a: Broadcast, b: Broadcast) => (a.id > b.id ? a : b))
                    setSelectedBroadcastId(newest.id)
                  }
                }}
                onCancel={() => setShowCreateBroadcast(false)}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
