// ReminderEditor — секция напоминалок в форме рассылки

import { useState } from 'react'
import type { BroadcastReminder, BroadcastButton, ReminderTriggerType } from '@/types'
import { MessageEditor } from './MessageEditor'
import { PhotoUploader } from './PhotoUploader'
import { PollEditor } from './PollEditor'
import { ButtonEditor } from './ButtonEditor'
import styles from './ReminderEditor.module.css'

interface Props {
  reminders: BroadcastReminder[]
  onChange: (reminders: BroadcastReminder[]) => void
  parentButtons: BroadcastButton[]
  hasDiscountButton: boolean
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Ожидает',
  scheduled: 'Запланирована',
  sending: 'Отправляется',
  sent: 'Отправлена',
  cancelled: 'Отменена',
  skipped: 'Пропущена',
}

function formatOffsetHours(offset: number): string {
  const h = Math.floor(offset)
  const m = Math.round((offset % 1) * 60)
  if (m === 0) return `${h}ч`
  if (h === 0) return `${m}мин`
  return `${h}ч ${m}мин`
}

function reminderSummary(r: BroadcastReminder, hasDiscount: boolean): string {
  const parts: string[] = []
  const time = formatOffsetHours(r.offset_hours)
  if (r.trigger_type === 'before_discount_end' && hasDiscount) {
    parts.push(`За ${time} до конца скидки`)
  } else {
    parts.push(`Через ${time} после отправки`)
  }
  if (r.exclude_bought) parts.push('исключая купивших')
  if (r.exclude_clicked_buttons?.length) parts.push(`исключая ${r.exclude_clicked_buttons.length} кнопок`)
  return parts.join(', ')
}

function createEmptyReminder(sortOrder: number): BroadcastReminder {
  return {
    sort_order: sortOrder,
    message_text: null,
    photo_path: null,
    inline_buttons: null,
    poll_question: null,
    poll_options: null,
    poll_is_anonymous: true,
    poll_allows_multiple: false,
    offset_hours: 2,
    trigger_type: 'after_send',
    exclude_bought: false,
    exclude_clicked_buttons: null,
  }
}

export function ReminderEditor({ reminders, onChange, parentButtons, hasDiscountButton }: Props) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  const addReminder = () => {
    const next = [...reminders, createEmptyReminder(reminders.length)]
    onChange(next)
    setExpandedIdx(next.length - 1)
  }

  const removeReminder = (idx: number) => {
    const next = reminders.filter((_, i) => i !== idx)
    onChange(next)
    if (expandedIdx === idx) setExpandedIdx(null)
    else if (expandedIdx !== null && expandedIdx > idx) setExpandedIdx(expandedIdx - 1)
  }

  const updateReminder = (idx: number, patch: Partial<BroadcastReminder>) => {
    const next = reminders.map((r, i) => (i === idx ? { ...r, ...patch } : r))
    onChange(next)
  }

  // Кнопки родителя с option_key (для фильтрации exclude_clicked)
  const parentQuickReplyButtons = parentButtons.filter(b => b.type === 'quick_reply' && b.option_key)

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.title}>Напоминалки</span>
        <button className={styles.addButton} onClick={addReminder} type="button">
          + Добавить напоминание
        </button>
      </div>

      {reminders.length === 0 && (
        <div className={styles.empty}>Нет напоминалок. Добавьте, чтобы автоматически отправить сообщение после рассылки.</div>
      )}

      {reminders.map((reminder, idx) => {
        const isExpanded = expandedIdx === idx
        const isReadOnly = !!reminder.reminder_status && !['pending', undefined].includes(reminder.reminder_status as string)

        return (
          <div key={reminder.id ?? `new-${idx}`} className={styles.card}>
            {/* Header */}
            <div className={styles.cardHeader} onClick={() => setExpandedIdx(isExpanded ? null : idx)}>
              <div className={styles.cardHeaderLeft}>
                <span className={`${styles.expandIcon} ${isExpanded ? styles.expandIconOpen : ''}`}>
                  ▶
                </span>
                <span className={styles.cardTitle}>
                  Напоминание #{idx + 1}
                </span>
                {!isExpanded && (
                  <span className={styles.cardSummary}>
                    {reminderSummary(reminder, hasDiscountButton)}
                  </span>
                )}
              </div>

              {reminder.reminder_status && reminder.reminder_status !== 'pending' && (
                <span className={`${styles.cardStatus} ${styles[`status_${reminder.reminder_status}`]}`}>
                  {STATUS_LABELS[reminder.reminder_status] || reminder.reminder_status}
                </span>
              )}

              {!isReadOnly && (
                <button
                  className={styles.deleteButton}
                  onClick={(e) => { e.stopPropagation(); removeReminder(idx) }}
                  title="Удалить"
                >
                  ×
                </button>
              )}
            </div>

            {/* Body */}
            {isExpanded && (
              <div className={styles.cardBody}>
                {/* Timing */}
                <div className={styles.timingRow}>
                  <div className={styles.field}>
                    <span className={styles.fieldLabel}>Тип тайминга</span>
                    <select
                      className={styles.select}
                      value={reminder.trigger_type}
                      onChange={(e) => updateReminder(idx, { trigger_type: e.target.value as ReminderTriggerType })}
                      disabled={isReadOnly}
                    >
                      <option value="after_send">После отправки рассылки</option>
                      {hasDiscountButton && (
                        <option value="before_discount_end">До конца скидки</option>
                      )}
                    </select>
                  </div>

                  <div className={styles.field}>
                    <span className={styles.fieldLabel}>
                      {reminder.trigger_type === 'before_discount_end' ? 'За сколько' : 'Через сколько'}
                    </span>
                    <div className={styles.timeInputs}>
                      <label className={styles.timeInputGroup}>
                        <input
                          className={styles.numberInput}
                          type="number"
                          min={0}
                          step={1}
                          value={Math.floor(reminder.offset_hours)}
                          onChange={(e) => {
                            const h = parseInt(e.target.value) || 0
                            const m = Math.round((reminder.offset_hours % 1) * 60)
                            updateReminder(idx, { offset_hours: h + m / 60 })
                          }}
                          disabled={isReadOnly}
                        />
                        <span className={styles.timeUnit}>ч</span>
                      </label>
                      <label className={styles.timeInputGroup}>
                        <input
                          className={styles.numberInput}
                          type="number"
                          min={0}
                          max={59}
                          step={5}
                          value={Math.round((reminder.offset_hours % 1) * 60)}
                          onChange={(e) => {
                            const h = Math.floor(reminder.offset_hours)
                            const m = parseInt(e.target.value) || 0
                            updateReminder(idx, { offset_hours: h + Math.min(m, 59) / 60 })
                          }}
                          disabled={isReadOnly}
                        />
                        <span className={styles.timeUnit}>мин</span>
                      </label>
                    </div>
                  </div>
                </div>

                {/* Filters */}
                <div className={styles.filtersSection}>
                  <span className={styles.filterLabel}>Фильтрация аудитории</span>

                  <label className={styles.checkboxRow}>
                    <input
                      type="checkbox"
                      checked={reminder.exclude_bought}
                      onChange={(e) => updateReminder(idx, { exclude_bought: e.target.checked })}
                      disabled={isReadOnly}
                    />
                    Исключить купивших после рассылки
                  </label>

                  {parentQuickReplyButtons.length > 0 && (
                    <div>
                      <span className={styles.filterLabel}>Исключить кликнувших кнопки:</span>
                      <div className={styles.buttonChips}>
                        {parentQuickReplyButtons.map((btn) => {
                          const key = btn.option_key!
                          const isActive = reminder.exclude_clicked_buttons?.includes(key)
                          return (
                            <button
                              key={key}
                              type="button"
                              className={`${styles.chip} ${isActive ? styles.chipActive : ''}`}
                              disabled={isReadOnly}
                              onClick={() => {
                                const current = reminder.exclude_clicked_buttons || []
                                const next = isActive
                                  ? current.filter(k => k !== key)
                                  : [...current, key]
                                updateReminder(idx, { exclude_clicked_buttons: next.length > 0 ? next : null })
                              }}
                            >
                              {btn.text || key}
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Content */}
                {!isReadOnly && (
                  <div className={styles.contentSection}>
                    <span className={styles.contentLabel}>Содержимое напоминания</span>

                    <MessageEditor
                      value={reminder.message_text || ''}
                      onChange={(val) => updateReminder(idx, { message_text: val })}
                    />

                    <PhotoUploader
                      photoPath={reminder.photo_path || ''}
                      onPhotoChange={(val) => updateReminder(idx, { photo_path: val })}
                    />

                    <PollEditor
                      pollQuestion={reminder.poll_question || ''}
                      pollOptions={reminder.poll_options || ['', '']}
                      pollAllowsMultiple={reminder.poll_allows_multiple}
                      onChange={({ question, options, allowsMultiple }) => {
                        const patch: Partial<BroadcastReminder> = {}
                        if (question !== undefined) patch.poll_question = question
                        if (options !== undefined) patch.poll_options = options
                        if (allowsMultiple !== undefined) patch.poll_allows_multiple = allowsMultiple
                        updateReminder(idx, patch)
                      }}
                    />

                    <ButtonEditor
                      buttons={reminder.inline_buttons || []}
                      onChange={(btns) => updateReminder(idx, { inline_buttons: btns })}
                    />
                  </div>
                )}

                {/* Read-only status info */}
                {isReadOnly && (
                  <div className={styles.filtersSection}>
                    {reminder.reminder_scheduled_at && (
                      <div className={styles.checkboxRow}>
                        Запланирована на: {new Date(reminder.reminder_scheduled_at).toLocaleString('ru-RU')}
                      </div>
                    )}
                    {reminder.total_recipients !== undefined && (
                      <div className={styles.checkboxRow}>
                        Получателей: {reminder.total_recipients} | Доставлено: {reminder.sent_count ?? 0} | Ошибок: {reminder.failed_count ?? 0}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
