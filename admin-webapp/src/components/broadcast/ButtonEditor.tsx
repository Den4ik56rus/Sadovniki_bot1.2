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
  is_active: boolean
}

interface Props {
  buttons: BroadcastButton[]
  onChange: (buttons: BroadcastButton[]) => void
}

const MAX_ROWS = 5
const MAX_BUTTONS_PER_ROW = 2

export function ButtonEditor({ buttons, onChange }: Props) {
  const [enabled, setEnabled] = useState(buttons.length > 0)
  const [plans, setPlans] = useState<SubscriptionPlan[]>([])
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

  useEffect(() => {
    if (hasPaymentButton && plans.length === 0) {
      api.getSubscriptionPlans().then((data) => {
        setPlans((data.plans as SubscriptionPlan[]).filter((p) => p.is_active))
      }).catch(() => {})
    }
  }, [hasPaymentButton, plans.length])

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
                            const newType = e.target.value as 'url' | 'quick_reply' | 'payment'
                            const optIdx = buttons.length
                            if (newType === 'payment' && plans.length === 0) {
                              api.getSubscriptionPlans().then((data) => {
                                setPlans((data.plans as SubscriptionPlan[]).filter((p) => p.is_active))
                              }).catch(() => {})
                            }
                            updateButton(rowIdx, btnIdx, {
                              type: newType,
                              url: newType === 'url' ? (btn.url || '') : undefined,
                              option_key: btn.option_key || `opt_${optIdx}`,
                              reply_text: newType !== 'quick_reply' ? undefined : btn.reply_text,
                              payment_plan_id: newType === 'payment' ? (btn.payment_plan_id ?? null) : undefined,
                              payment_custom_price: newType === 'payment' ? (btn.payment_custom_price ?? null) : undefined,
                              payment_bonus_tokens: newType === 'payment' ? (btn.payment_bonus_tokens ?? null) : undefined,
                            })
                          }}
                        >
                          <option value="quick_reply">Ответ</option>
                          <option value="url">Ссылка</option>
                          <option value="payment">💳 Оплата</option>
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
                        {btn.type === 'payment' && (
                          <div className={styles.paymentSection}>
                            <select
                              className={styles.typeSelect}
                              value={btn.payment_plan_id ?? ''}
                              onChange={(e) => updateButton(rowIdx, btnIdx, {
                                payment_plan_id: e.target.value ? Number(e.target.value) : null
                              })}
                            >
                              <option value="">Выберите тариф</option>
                              {plans.map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.name} — {p.price_rub}₽/мес
                                </option>
                              ))}
                            </select>
                            <div className={styles.paymentFields}>
                              <input
                                className={styles.urlInput}
                                type="number"
                                placeholder={
                                  btn.payment_plan_id
                                    ? String(plans.find((p) => p.id === btn.payment_plan_id)?.price_rub ?? 'цена')
                                    : 'Цена (₽)'
                                }
                                value={btn.payment_custom_price ?? ''}
                                min={1}
                                onChange={(e) => updateButton(rowIdx, btnIdx, {
                                  payment_custom_price: e.target.value ? Number(e.target.value) : null
                                })}
                              />
                              <input
                                className={styles.urlInput}
                                type="number"
                                placeholder="Бонус токенов"
                                value={btn.payment_bonus_tokens ?? ''}
                                min={0}
                                onChange={(e) => updateButton(rowIdx, btnIdx, {
                                  payment_bonus_tokens: e.target.value ? Number(e.target.value) : null
                                })}
                              />
                            </div>
                            {btn.payment_plan_id && (() => {
                              const plan = plans.find((p) => p.id === btn.payment_plan_id)
                              if (!plan) return null
                              const price = btn.payment_custom_price ?? plan.price_rub
                              const tokens = plan.tokens_included + (btn.payment_bonus_tokens ?? 0)
                              const discount = btn.payment_custom_price && btn.payment_custom_price < plan.price_rub
                                ? Math.round((1 - btn.payment_custom_price / plan.price_rub) * 100)
                                : 0
                              return (
                                <div className={styles.paymentHint}>
                                  {discount > 0
                                    ? <><s>{plan.price_rub}₽</s> → <b>{price}₽</b>/мес (скидка {discount}%)</>
                                    : <><b>{price}₽</b>/мес</>
                                  }
                                  {' · '}{tokens} токенов/мес
                                </div>
                              )
                            })()}
                            <div className={styles.urlHint}>
                              Пользователь получит персональную ссылку оплаты на YooKassa
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
