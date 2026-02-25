// Button Editor — редактор inline-кнопок для рассылки

import { useState, useEffect } from 'react'
import type { BroadcastButton } from '@/types'
import { MessageEditor } from './MessageEditor'
import { api } from '@/services/api'
import styles from './ButtonEditor.module.css'

interface SubscriptionPlan {
  id: number
  name: string
  price_rub: number
  tokens_included: number
  duration_days: number
  is_active: boolean
}

interface TokenPackage {
  id: number
  name: string
  description: string | null
  price_rub: number
  tokens_amount: number
  is_active: boolean
}

interface Props {
  buttons: BroadcastButton[]
  onChange: (buttons: BroadcastButton[]) => void
  onAutoFillMessage?: (html: string) => void
}

const MAX_ROWS = 5
const MAX_BUTTONS_PER_ROW = 2

function buildPaymentButtonText(plan: SubscriptionPlan, customPrice: number | null | undefined): string {
  const price = customPrice ?? plan.price_rub
  const discount = customPrice && customPrice < plan.price_rub
    ? Math.round((1 - customPrice / plan.price_rub) * 100)
    : 0
  return discount > 0
    ? `💳 ${plan.name} — ${price}₽ (скидка ${discount}%)`
    : `💳 ${plan.name} — ${price}₽`
}

function buildTokenButtonText(pkg: TokenPackage, customPrice: number | null | undefined): string {
  const price = customPrice ?? pkg.price_rub
  const discount = customPrice && customPrice < pkg.price_rub
    ? Math.round((1 - customPrice / pkg.price_rub) * 100)
    : 0
  return discount > 0
    ? `🎁 ${pkg.tokens_amount} токенов — ${price}₽ (скидка ${discount}%)`
    : `🎁 ${pkg.tokens_amount} токенов — ${price}₽`
}

function formatDurationHours(durationHours: number | null | undefined): string {
  const total = durationHours ?? 24
  const h = Math.floor(total)
  const m = Math.round((total % 1) * 60)
  if (m === 0) return `${h}ч`
  if (h === 0) return `${m}мин`
  return `${h}ч ${m}мин`
}

function buildDiscountButtonText(discountPercent: number | null | undefined, durationHours: number | null | undefined, bonusTokens?: number | null, bonusMode?: 'absolute' | 'percent'): string {
  const pct = discountPercent ?? 0
  const timeStr = formatDurationHours(durationHours)
  if (pct > 0 && bonusTokens && bonusTokens > 0) {
    return bonusMode === 'percent'
      ? `🏷️ Скидка ${pct}% + ${bonusTokens}% токенов`
      : `🏷️ Скидка ${pct}% + ${bonusTokens} токенов`
  }
  if (pct > 0) return `🏷️ Скидка ${pct}% на ${timeStr}`
  if (bonusTokens && bonusTokens > 0) {
    return bonusMode === 'percent'
      ? `🎁 +${bonusTokens}% бонус-токенов`
      : `🎁 +${bonusTokens} бонус-токенов`
  }
  return `🏷️ Скидка на ${timeStr}`
}

function buildDiscountMessageHtml(discountPercent: number | null | undefined, durationHours: number | null | undefined, bonusTokens: number | null | undefined, bonusMode?: 'absolute' | 'percent'): string {
  const pct = discountPercent ?? 0
  const hours = durationHours ?? 24
  const timeStr = hours >= 24 && hours % 1 === 0
    ? `${Math.floor(hours / 24)} ${Math.floor(hours / 24) === 1 ? 'день' : Math.floor(hours / 24) < 5 ? 'дня' : 'дней'}`
    : formatDurationHours(hours)
  let bonusLine = ''
  if (bonusTokens && bonusTokens > 0) {
    if (bonusMode === 'percent') {
      bonusLine = `<p>🎁 Бонус: +${bonusTokens}% токенов к тарифу при оформлении</p>`
    } else {
      bonusLine = `<p>🎁 Бонус: +${bonusTokens} токенов при оформлении</p>`
    }
  }
  // Если скидка 0%, но есть бонус — другой заголовок
  const headline = pct > 0
    ? `<p>🔥 <strong>Персональная скидка ${pct}% на все тарифы</strong></p>`
    : `<p>🎁 <strong>Персональный бонус для вас</strong></p>`
  const actionLine = pct > 0
    ? `<p>Нажмите кнопку ниже, чтобы выбрать тариф со скидкой.</p>`
    : `<p>Нажмите кнопку ниже, чтобы выбрать тариф с бонусом.</p>`
  return [
    headline,
    `<p>Действует ${timeStr} — только для вас.</p>`,
    bonusLine,
    `<p></p>`,
    actionLine,
  ].filter(Boolean).join('')
}

function buildTokenMessageHtml(pkg: TokenPackage, customPrice: number | null | undefined): string {
  const price = customPrice ?? pkg.price_rub
  const discount = customPrice && customPrice < pkg.price_rub
    ? Math.round((1 - customPrice / pkg.price_rub) * 100)
    : 0
  const priceLine = discount > 0
    ? `💰 Цена: <s>${pkg.price_rub}₽</s> → <strong>${price}₽</strong> (скидка ${discount}%)`
    : `💰 Цена: <strong>${price}₽</strong>`
  return [
    `🎁 Дополнительные токены: <strong>${pkg.tokens_amount} шт.</strong>`,
    priceLine,
    ``,
    `Нажмите кнопку ниже для оплаты.`,
    `После успешной оплаты токены будут начислены автоматически.`,
  ].map(line => `<p>${line}</p>`).join('')
}

function buildPaymentMessageHtml(plan: SubscriptionPlan, customPrice: number | null | undefined, bonusTokens: number | null | undefined): string {
  const price = customPrice ?? plan.price_rub
  const tokens = plan.tokens_included + (bonusTokens ?? 0)
  const discount = customPrice && customPrice < plan.price_rub
    ? Math.round((1 - customPrice / plan.price_rub) * 100)
    : 0

  const priceLine = discount > 0
    ? `💰 Цена: <s>${plan.price_rub}₽</s> → <strong>${price}₽</strong>/мес (скидка ${discount}%)`
    : `💰 Цена: <strong>${price}₽</strong>/мес`

  const tokensLine = bonusTokens
    ? `🎁 Лимит: ${tokens} токенов в месяц (+${bonusTokens} бонус)`
    : `🎁 Лимит: ${tokens} токенов в месяц`

  return [
    `📅 Подписка: <strong>${plan.name}</strong>`,
    priceLine,
    `⏱️ Срок: ${plan.duration_days} дней`,
    tokensLine,
    ``,
    `Нажмите кнопку ниже для оплаты.`,
    `После успешной оплаты подписка будет активирована автоматически.`,
  ].map(line => `<p>${line}</p>`).join('')
}

export function ButtonEditor({ buttons, onChange, onAutoFillMessage }: Props) {
  const [enabled, setEnabled] = useState(buttons.length > 0)
  const [plans, setPlans] = useState<SubscriptionPlan[]>([])
  const [tokenPackages, setTokenPackages] = useState<TokenPackage[]>([])
  const [expandedReplies, setExpandedReplies] = useState<Set<string>>(() => {
    const initial = new Set<string>()
    const rowsMap: Record<number, BroadcastButton[]> = {}
    for (const btn of buttons) {
      const r = btn.row ?? 0
      if (!rowsMap[r]) rowsMap[r] = []
      rowsMap[r].push(btn)
    }
    for (const [rowIdx, rowBtns] of Object.entries(rowsMap)) {
      rowBtns.forEach((btn, btnIdx) => {
        if (btn.reply_text) {
          initial.add(`${rowIdx}_${btnIdx}`)
        }
      })
    }
    return initial
  })

  const hasPaymentButton = buttons.some((b) => b.type === 'payment')
  const hasDiscountButton = buttons.some((b) => b.type === 'discount')

  useEffect(() => {
    if (hasPaymentButton || hasDiscountButton) {
      if (plans.length === 0) {
        api.getSubscriptionPlans().then((data) => {
          setPlans((data.plans as SubscriptionPlan[]).filter((p) => p.is_active))
        }).catch(() => {})
      }
    }
    if (hasPaymentButton) {
      if (tokenPackages.length === 0) {
        api.getTokenPackages().then((data) => {
          setTokenPackages((data.packages as TokenPackage[]).filter((p) => p.is_active))
        }).catch(() => {})
      }
    }
  }, [hasPaymentButton, hasDiscountButton, plans.length, tokenPackages.length])

  const handleToggle = () => {
    const next = !enabled
    setEnabled(next)
    if (!next) {
      onChange([])
    }
  }

  // Группируем кнопки по рядам
  const rows: Record<number, BroadcastButton[]> = {}
  for (const btn of buttons) {
    const r = btn.row ?? 0
    if (!rows[r]) rows[r] = []
    rows[r].push(btn)
  }
  const rowKeys = Object.keys(rows).map(Number).sort((a, b) => a - b)
  const rowCount = rowKeys.length || 0

  const updateButton = (rowIdx: number, btnIdx: number, updates: Partial<BroadcastButton>) => {
    const updated = buttons.map((b) => {
      // Находим кнопку в нужном ряду
      const rowButtons = buttons.filter((x) => x.row === rowIdx)
      if (b === rowButtons[btnIdx]) {
        return { ...b, ...updates }
      }
      return b
    })
    onChange(updated)
  }

  const addRow = () => {
    const newRow = rowCount > 0 ? Math.max(...rowKeys) + 1 : 0
    const optIdx = buttons.filter((b) => b.type === 'quick_reply').length
    onChange([...buttons, {
      row: newRow,
      text: '',
      type: 'quick_reply',
      option_key: `opt_${optIdx}`,
    }])
  }

  const addButtonToRow = (rowIdx: number) => {
    const rowButtons = buttons.filter((b) => b.row === rowIdx)
    if (rowButtons.length >= MAX_BUTTONS_PER_ROW) return
    const optIdx = buttons.filter((b) => b.type === 'quick_reply').length
    onChange([...buttons, {
      row: rowIdx,
      text: '',
      type: 'quick_reply',
      option_key: `opt_${optIdx}`,
    }])
  }

  const removeButton = (rowIdx: number, btnIdx: number) => {
    const rowButtons = buttons.filter((b) => b.row === rowIdx)
    const target = rowButtons[btnIdx]
    const updated = buttons.filter((b) => b !== target)
    // Если ряд стал пустым — ничего не делаем, ряд просто исчезнет
    onChange(updated)
  }

  const removeRow = (rowIdx: number) => {
    onChange(buttons.filter((b) => b.row !== rowIdx))
  }

  const toggleReplyEditor = (rowIdx: number, btnIdx: number) => {
    const key = `${rowIdx}_${btnIdx}`
    setExpandedReplies((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  return (
    <div className={styles.container}>
      <label className={styles.toggleLabel}>
        <input
          type="checkbox"
          checked={enabled}
          onChange={handleToggle}
        />
        <span>Добавить кнопки</span>
      </label>

      {enabled && (
        <div className={styles.editorForm}>
          {rowKeys.map((rowIdx) => {
            const rowButtons = buttons.filter((b) => b.row === rowIdx)
            return (
              <div key={rowIdx} className={styles.rowBlock}>
                <div className={styles.rowHeader}>
                  <span className={styles.rowLabel}>Ряд {rowIdx + 1}</span>
                  <button
                    className={styles.removeRowBtn}
                    onClick={() => removeRow(rowIdx)}
                    type="button"
                    title="Удалить ряд"
                  >
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M3 3L9 9M9 3L3 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  </button>
                </div>
                <div className={styles.rowButtons}>
                  {rowButtons.map((btn, btnIdx) => (
                    <div key={btnIdx} className={styles.buttonCard}>
                      <div className={styles.buttonFields}>
                        <input
                          className={styles.buttonTextInput}
                          type="text"
                          placeholder="Текст кнопки"
                          value={btn.text}
                          maxLength={64}
                          onChange={(e) => updateButton(rowIdx, btnIdx, { text: e.target.value })}
                        />
                        <select
                          className={styles.typeSelect}
                          value={btn.type}
                          onChange={(e) => {
                            const newType = e.target.value as 'url' | 'quick_reply' | 'payment' | 'discount'
                            const optIdx = buttons.length
                            if (newType === 'payment') {
                              if (plans.length === 0) {
                                api.getSubscriptionPlans().then((data) => {
                                  setPlans((data.plans as SubscriptionPlan[]).filter((p) => p.is_active))
                                }).catch(() => {})
                              }
                              if (tokenPackages.length === 0) {
                                api.getTokenPackages().then((data) => {
                                  setTokenPackages((data.packages as TokenPackage[]).filter((p) => p.is_active))
                                }).catch(() => {})
                              }
                            }
                            updateButton(rowIdx, btnIdx, {
                              type: newType,
                              url: newType === 'url' ? (btn.url || '') : undefined,
                              option_key: btn.option_key || `opt_${optIdx}`,
                              reply_text: newType !== 'quick_reply' ? undefined : btn.reply_text,
                              payment_plan_id: newType === 'payment' ? (btn.payment_plan_id ?? null) : undefined,
                              payment_custom_price: newType === 'payment' ? (btn.payment_custom_price ?? null) : undefined,
                              payment_bonus_tokens: newType === 'payment' ? (btn.payment_bonus_tokens ?? null) : undefined,
                              payment_package_id: newType === 'payment' ? (btn.payment_package_id ?? null) : undefined,
                              discount_percent: newType === 'discount' ? (btn.discount_percent ?? null) : undefined,
                              discount_bonus_tokens: newType === 'discount' ? (btn.discount_bonus_tokens ?? null) : undefined,
                              discount_bonus_tokens_mode: newType === 'discount' ? (btn.discount_bonus_tokens_mode ?? 'absolute') : undefined,
                              discount_duration_hours: newType === 'discount' ? (btn.discount_duration_hours ?? null) : undefined,
                            })
                          }}
                        >
                          <option value="quick_reply">Ответ</option>
                          <option value="url">Ссылка</option>
                          <option value="payment">💳 Оплата</option>
                          <option value="discount">🏷️ Скидка на все тарифы</option>
                        </select>
                        {btn.type === 'url' && (
                          <input
                            className={styles.urlInput}
                            type="url"
                            placeholder="https://..."
                            value={btn.url || ''}
                            onChange={(e) => updateButton(rowIdx, btnIdx, { url: e.target.value })}
                          />
                        )}
                        {btn.type === 'url' && (
                          <div className={styles.urlHint}>
                            Откроет ссылку сразу в браузере
                          </div>
                        )}
                        {btn.type === 'quick_reply' && (
                          <div className={styles.replySection}>
                            <button
                              className={styles.replyToggle}
                              onClick={() => toggleReplyEditor(rowIdx, btnIdx)}
                              type="button"
                            >
                              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                                <path
                                  d={expandedReplies.has(`${rowIdx}_${btnIdx}`) ? 'M2 3.5L5 6.5L8 3.5' : 'M3.5 2L6.5 5L3.5 8'}
                                  stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
                                />
                              </svg>
                              {btn.reply_text ? 'Редактировать ответ' : 'Добавить ответ'}
                            </button>
                            {expandedReplies.has(`${rowIdx}_${btnIdx}`) && (
                              <div className={styles.replyEditor}>
                                <MessageEditor
                                  value={btn.reply_text || ''}
                                  onChange={(html) => {
                                    const clean = html.replace(/<p><\/p>/g, '').trim()
                                    updateButton(rowIdx, btnIdx, { reply_text: clean || undefined })
                                  }}
                                />
                                <div className={styles.replyHint}>
                                  Это сообщение будет отправлено пользователю при нажатии на кнопку
                                </div>
                              </div>
                            )}
                            <label className={styles.askResponseLabel}>
                              <input
                                type="checkbox"
                                checked={btn.ask_for_response || false}
                                onChange={(e) => updateButton(rowIdx, btnIdx, { ask_for_response: e.target.checked || undefined })}
                              />
                              <span>Запросить текстовый ответ</span>
                            </label>
                            {btn.ask_for_response && (
                              <div className={styles.replyHint}>
                                После нажатия бот попросит пользователя написать ответ. Ответы будут видны в статистике.
                              </div>
                            )}
                          </div>
                        )}
                        {btn.type === 'payment' && (() => {
                          // Определяем режим: подписка или токены
                          // payment_package_id >= 0 (включая 0 как sentinel) = режим токенов
                          const paymentMode = btn.payment_package_id != null ? 'tokens' : 'subscription'

                          const selectedPlan = plans.find((p) => p.id === btn.payment_plan_id)
                          // Ищем только если package_id > 0 (0 = режим токенов, пакет ещё не выбран)
                          const selectedPkg = btn.payment_package_id && btn.payment_package_id > 0
                            ? tokenPackages.find((p) => p.id === btn.payment_package_id)
                            : undefined

                          // Subscription preview
                          const subPrice = selectedPlan ? (btn.payment_custom_price ?? selectedPlan.price_rub) : null
                          const subTokens = selectedPlan ? (selectedPlan.tokens_included + (btn.payment_bonus_tokens ?? 0)) : null
                          const subDiscount = selectedPlan && btn.payment_custom_price && btn.payment_custom_price < selectedPlan.price_rub
                            ? Math.round((1 - btn.payment_custom_price / selectedPlan.price_rub) * 100)
                            : 0

                          // Token preview
                          const pkgPrice = selectedPkg ? (btn.payment_custom_price ?? selectedPkg.price_rub) : null
                          const pkgDiscount = selectedPkg && btn.payment_custom_price && btn.payment_custom_price < selectedPkg.price_rub
                            ? Math.round((1 - btn.payment_custom_price / selectedPkg.price_rub) * 100)
                            : 0

                          return (
                            <div className={styles.paymentSection}>
                              {/* Выбор типа платежа */}
                              <div className={styles.paymentModeRow}>
                                <label className={styles.paymentModeOption}>
                                  <input
                                    type="radio"
                                    name={`paymentMode_${rowIdx}_${btnIdx}`}
                                    value="subscription"
                                    checked={paymentMode === 'subscription'}
                                    onChange={() => updateButton(rowIdx, btnIdx, {
                                      payment_package_id: null,
                                      payment_plan_id: btn.payment_plan_id ?? null,
                                    })}
                                  />
                                  <span>Подписка</span>
                                </label>
                                <label className={styles.paymentModeOption}>
                                  <input
                                    type="radio"
                                    name={`paymentMode_${rowIdx}_${btnIdx}`}
                                    value="tokens"
                                    checked={paymentMode === 'tokens'}
                                    onChange={() => updateButton(rowIdx, btnIdx, {
                                      payment_plan_id: null,
                                      payment_bonus_tokens: null,
                                      // 0 = sentinel: режим токенов, но пакет ещё не выбран
                                      payment_package_id: btn.payment_package_id ?? 0,
                                    })}
                                  />
                                  <span>Доп. токены</span>
                                </label>
                              </div>

                              {paymentMode === 'subscription' && (
                                <>
                                  <select
                                    className={styles.typeSelect}
                                    value={btn.payment_plan_id ?? ''}
                                    onChange={(e) => {
                                      const planId = e.target.value ? Number(e.target.value) : null
                                      const plan = plans.find((p) => p.id === planId)
                                      const autoText = plan ? buildPaymentButtonText(plan, btn.payment_custom_price) : ''
                                      updateButton(rowIdx, btnIdx, {
                                        payment_plan_id: planId,
                                        text: autoText,
                                      })
                                      if (plan && onAutoFillMessage) {
                                        onAutoFillMessage(buildPaymentMessageHtml(plan, btn.payment_custom_price, btn.payment_bonus_tokens))
                                      }
                                    }}
                                  >
                                    <option value="">Выберите тариф</option>
                                    {plans.map((p) => (
                                      <option key={p.id} value={p.id}>
                                        {p.name} — {p.price_rub}₽/мес
                                      </option>
                                    ))}
                                  </select>
                                  {selectedPlan && (
                                    <div className={styles.paymentFields}>
                                      <div className={styles.paymentFieldGroup}>
                                        <label className={styles.paymentFieldLabel}>Скидочная цена (₽)</label>
                                        <input
                                          className={styles.urlInput}
                                          type="number"
                                          placeholder={String(selectedPlan.price_rub)}
                                          value={btn.payment_custom_price ?? ''}
                                          min={1}
                                          onChange={(e) => {
                                            const customPrice = e.target.value ? Number(e.target.value) : null
                                            const autoText = buildPaymentButtonText(selectedPlan, customPrice)
                                            updateButton(rowIdx, btnIdx, {
                                              payment_custom_price: customPrice,
                                              text: autoText,
                                            })
                                            if (onAutoFillMessage) {
                                              onAutoFillMessage(buildPaymentMessageHtml(selectedPlan, customPrice, btn.payment_bonus_tokens))
                                            }
                                          }}
                                        />
                                      </div>
                                      <div className={styles.paymentFieldGroup}>
                                        <label className={styles.paymentFieldLabel}>Бонус токенов</label>
                                        <input
                                          className={styles.urlInput}
                                          type="number"
                                          placeholder="0"
                                          value={btn.payment_bonus_tokens ?? ''}
                                          min={0}
                                          onChange={(e) => {
                                            const bonusTokens = e.target.value ? Number(e.target.value) : null
                                            updateButton(rowIdx, btnIdx, {
                                              payment_bonus_tokens: bonusTokens,
                                            })
                                            if (onAutoFillMessage) {
                                              onAutoFillMessage(buildPaymentMessageHtml(selectedPlan, btn.payment_custom_price, bonusTokens))
                                            }
                                          }}
                                        />
                                      </div>
                                    </div>
                                  )}
                                  {selectedPlan && subPrice !== null && (
                                    <div className={styles.paymentHint}>
                                      {subDiscount > 0
                                        ? <><s>{selectedPlan.price_rub}₽</s> → <b>{subPrice}₽</b>/мес (скидка {subDiscount}%) · {subTokens} токенов</>
                                        : <><b>{subPrice}₽</b>/мес · {subTokens} токенов</>
                                      }
                                    </div>
                                  )}
                                </>
                              )}

                              {paymentMode === 'tokens' && (
                                <>
                                  <select
                                    className={styles.typeSelect}
                                    value={btn.payment_package_id && btn.payment_package_id > 0 ? btn.payment_package_id : ''}
                                    onChange={(e) => {
                                      const pkgId = e.target.value ? Number(e.target.value) : 0
                                      const pkg = tokenPackages.find((p) => p.id === pkgId)
                                      const autoText = pkg ? buildTokenButtonText(pkg, btn.payment_custom_price) : ''
                                      updateButton(rowIdx, btnIdx, {
                                        payment_package_id: pkgId,
                                        text: autoText,
                                      })
                                      if (pkg && onAutoFillMessage) {
                                        onAutoFillMessage(buildTokenMessageHtml(pkg, btn.payment_custom_price))
                                      }
                                    }}
                                  >
                                    <option value="">Выберите пакет токенов</option>
                                    {tokenPackages.map((p) => (
                                      <option key={p.id} value={p.id}>
                                        {p.tokens_amount} токенов — {p.price_rub}₽
                                      </option>
                                    ))}
                                  </select>
                                  {selectedPkg && (
                                    <div className={styles.paymentFields}>
                                      <div className={styles.paymentFieldGroup}>
                                        <label className={styles.paymentFieldLabel}>Скидочная цена (₽)</label>
                                        <input
                                          className={styles.urlInput}
                                          type="number"
                                          placeholder={String(selectedPkg.price_rub)}
                                          value={btn.payment_custom_price ?? ''}
                                          min={1}
                                          onChange={(e) => {
                                            const customPrice = e.target.value ? Number(e.target.value) : null
                                            const autoText = buildTokenButtonText(selectedPkg, customPrice)
                                            updateButton(rowIdx, btnIdx, {
                                              payment_custom_price: customPrice,
                                              text: autoText,
                                            })
                                            if (onAutoFillMessage) {
                                              onAutoFillMessage(buildTokenMessageHtml(selectedPkg, customPrice))
                                            }
                                          }}
                                        />
                                      </div>
                                    </div>
                                  )}
                                  {selectedPkg && pkgPrice !== null && (
                                    <div className={styles.paymentHint}>
                                      {pkgDiscount > 0
                                        ? <><s>{selectedPkg.price_rub}₽</s> → <b>{pkgPrice}₽</b> (скидка {pkgDiscount}%) · {selectedPkg.tokens_amount} токенов</>
                                        : <><b>{pkgPrice}₽</b> · {selectedPkg.tokens_amount} токенов</>
                                      }
                                    </div>
                                  )}
                                </>
                              )}

                              <div className={styles.urlHint}>
                                Пользователь получит персональную ссылку оплаты на YooKassa
                              </div>
                            </div>
                          )
                        })()}
                        {btn.type === 'discount' && (
                          <div className={styles.paymentSection}>
                            <div className={styles.discountFieldsGrid}>
                              <div className={styles.paymentFieldGroup}>
                                <label className={styles.paymentFieldLabel}>Скидка (%)</label>
                                <input
                                  className={styles.urlInput}
                                  type="number"
                                  placeholder="30"
                                  value={btn.discount_percent ?? ''}
                                  min={0}
                                  max={99}
                                  onChange={(e) => {
                                    const pct = e.target.value ? Number(e.target.value) : null
                                    const autoText = buildDiscountButtonText(pct, btn.discount_duration_hours, btn.discount_bonus_tokens, btn.discount_bonus_tokens_mode)
                                    updateButton(rowIdx, btnIdx, {
                                      discount_percent: pct,
                                      text: autoText,
                                    })
                                    if (onAutoFillMessage) {
                                      onAutoFillMessage(buildDiscountMessageHtml(pct, btn.discount_duration_hours, btn.discount_bonus_tokens, btn.discount_bonus_tokens_mode))
                                    }
                                  }}
                                />
                              </div>
                              <div className={styles.paymentFieldGroup}>
                                <label className={styles.paymentFieldLabel}>Срок</label>
                                <div className={styles.durationInputs}>
                                  <label className={styles.durationInputGroup}>
                                    <input
                                      className={styles.durationInput}
                                      type="number"
                                      placeholder="24"
                                      value={btn.discount_duration_hours != null ? Math.floor(btn.discount_duration_hours) : ''}
                                      min={0}
                                      step={1}
                                      onChange={(e) => {
                                        const h = e.target.value !== '' ? parseInt(e.target.value) || 0 : 0
                                        const oldMin = btn.discount_duration_hours != null ? Math.round((btn.discount_duration_hours % 1) * 60) : 0
                                        const totalHours = h + oldMin / 60
                                        const hours = totalHours > 0 ? totalHours : null
                                        const autoText = buildDiscountButtonText(btn.discount_percent, hours, btn.discount_bonus_tokens, btn.discount_bonus_tokens_mode)
                                        updateButton(rowIdx, btnIdx, {
                                          discount_duration_hours: hours,
                                          text: autoText,
                                        })
                                        if (onAutoFillMessage) {
                                          onAutoFillMessage(buildDiscountMessageHtml(btn.discount_percent, hours, btn.discount_bonus_tokens, btn.discount_bonus_tokens_mode))
                                        }
                                      }}
                                    />
                                    <span className={styles.durationUnit}>ч</span>
                                  </label>
                                  <label className={styles.durationInputGroup}>
                                    <input
                                      className={styles.durationInput}
                                      type="number"
                                      placeholder="0"
                                      value={btn.discount_duration_hours != null ? Math.round((btn.discount_duration_hours % 1) * 60) : ''}
                                      min={0}
                                      max={59}
                                      step={5}
                                      onChange={(e) => {
                                        const m = e.target.value !== '' ? Math.min(parseInt(e.target.value) || 0, 59) : 0
                                        const oldH = btn.discount_duration_hours != null ? Math.floor(btn.discount_duration_hours) : 0
                                        const totalHours = oldH + m / 60
                                        const hours = totalHours > 0 ? totalHours : null
                                        const autoText = buildDiscountButtonText(btn.discount_percent, hours, btn.discount_bonus_tokens, btn.discount_bonus_tokens_mode)
                                        updateButton(rowIdx, btnIdx, {
                                          discount_duration_hours: hours,
                                          text: autoText,
                                        })
                                        if (onAutoFillMessage) {
                                          onAutoFillMessage(buildDiscountMessageHtml(btn.discount_percent, hours, btn.discount_bonus_tokens, btn.discount_bonus_tokens_mode))
                                        }
                                      }}
                                    />
                                    <span className={styles.durationUnit}>мин</span>
                                  </label>
                                </div>
                              </div>
                            </div>
                            <div className={styles.bonusSection}>
                              <label className={styles.paymentFieldLabel}>Бонус токенов</label>
                              <div className={styles.bonusModeRow}>
                                <label className={styles.paymentModeOption}>
                                  <input
                                    type="radio"
                                    name={`bonus_mode_${rowIdx}_${btnIdx}`}
                                    checked={(btn.discount_bonus_tokens_mode ?? 'absolute') === 'absolute'}
                                    onChange={() => {
                                      const autoText = buildDiscountButtonText(btn.discount_percent, btn.discount_duration_hours, null, 'absolute')
                                      updateButton(rowIdx, btnIdx, {
                                        discount_bonus_tokens_mode: 'absolute',
                                        discount_bonus_tokens: null,
                                        text: autoText,
                                      })
                                      if (onAutoFillMessage) {
                                        onAutoFillMessage(buildDiscountMessageHtml(btn.discount_percent, btn.discount_duration_hours, null, 'absolute'))
                                      }
                                    }}
                                  />
                                  <span>Число</span>
                                </label>
                                <label className={styles.paymentModeOption}>
                                  <input
                                    type="radio"
                                    name={`bonus_mode_${rowIdx}_${btnIdx}`}
                                    checked={btn.discount_bonus_tokens_mode === 'percent'}
                                    onChange={() => {
                                      const autoText = buildDiscountButtonText(btn.discount_percent, btn.discount_duration_hours, null, 'percent')
                                      updateButton(rowIdx, btnIdx, {
                                        discount_bonus_tokens_mode: 'percent',
                                        discount_bonus_tokens: null,
                                        text: autoText,
                                      })
                                      if (onAutoFillMessage) {
                                        onAutoFillMessage(buildDiscountMessageHtml(btn.discount_percent, btn.discount_duration_hours, null, 'percent'))
                                      }
                                    }}
                                  />
                                  <span>% от тарифа</span>
                                </label>
                              </div>
                              <div className={styles.bonusInputRow}>
                                <input
                                  className={styles.urlInput}
                                  type="number"
                                  placeholder={btn.discount_bonus_tokens_mode === 'percent' ? '20' : '0'}
                                  value={btn.discount_bonus_tokens ?? ''}
                                  min={0}
                                  max={btn.discount_bonus_tokens_mode === 'percent' ? 100 : undefined}
                                  onChange={(e) => {
                                    const bonus = e.target.value ? Number(e.target.value) : null
                                    const mode = btn.discount_bonus_tokens_mode ?? 'absolute'
                                    const autoText = buildDiscountButtonText(btn.discount_percent, btn.discount_duration_hours, bonus, mode)
                                    updateButton(rowIdx, btnIdx, {
                                      discount_bonus_tokens: bonus,
                                      text: autoText,
                                    })
                                    if (onAutoFillMessage) {
                                      onAutoFillMessage(buildDiscountMessageHtml(btn.discount_percent, btn.discount_duration_hours, bonus, mode))
                                    }
                                  }}
                                />
                                {btn.discount_bonus_tokens_mode === 'percent' && (
                                  <span className={styles.bonusPercent}>%</span>
                                )}
                              </div>
                              {btn.discount_bonus_tokens_mode === 'percent' && btn.discount_bonus_tokens && btn.discount_bonus_tokens > 0 && plans.length > 0 && (
                                <div className={styles.bonusCalcHint}>
                                  {plans.map((p) => `${p.name}: +${Math.ceil(p.tokens_included * btn.discount_bonus_tokens! / 100)}`).join(', ')}
                                </div>
                              )}
                            </div>
                            {btn.discount_percent && btn.discount_duration_hours && (
                              <div className={styles.paymentHint}>
                                При нажатии: откроется меню тарифов со скидкой <b>{btn.discount_percent}%</b> на <b>{formatDurationHours(btn.discount_duration_hours)}</b>
                                {btn.discount_bonus_tokens ? (
                                  btn.discount_bonus_tokens_mode === 'percent'
                                    ? ` + ${btn.discount_bonus_tokens}% бонус-токенов от тарифа`
                                    : ` + ${btn.discount_bonus_tokens} бонус-токенов`
                                ) : ''}
                              </div>
                            )}
                            <div className={styles.urlHint}>
                              Скидка действует на все тарифы. Пользователь провалится в специальное меню с зачёркнутыми ценами.
                            </div>
                          </div>
                        )}
                      </div>
                      <button
                        className={styles.removeBtnBtn}
                        onClick={() => removeButton(rowIdx, btnIdx)}
                        type="button"
                        title="Удалить кнопку"
                      >
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                          <path d="M3 3L9 9M9 3L3 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                        </svg>
                      </button>
                    </div>
                  ))}
                  {rowButtons.length < MAX_BUTTONS_PER_ROW && (
                    <button
                      className={styles.addBtnInRow}
                      onClick={() => addButtonToRow(rowIdx)}
                      type="button"
                    >
                      + кнопку
                    </button>
                  )}
                </div>
              </div>
            )
          })}

          {rowCount < MAX_ROWS && (
            <button
              className={styles.addRowBtn}
              onClick={addRow}
              type="button"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M6 1V11M1 6H11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              Добавить ряд кнопок
            </button>
          )}
        </div>
      )}
    </div>
  )
}
