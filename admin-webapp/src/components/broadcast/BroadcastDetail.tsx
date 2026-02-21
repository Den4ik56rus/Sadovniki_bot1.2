// Broadcast Detail — детальный просмотр рассылки

import { useEffect } from 'react'
import { useBroadcastStore } from '@/store/broadcastStore'
import type { BroadcastStatus } from '@/types'
import { BroadcastProgress } from './BroadcastProgress'
import { BroadcastStats } from './BroadcastStats'
import styles from './BroadcastDetail.module.css'

const STATUS_LABELS: Record<BroadcastStatus, string> = {
  draft: 'Черновик',
  scheduled: 'Запланирована',
  sending: 'Отправляется',
  completed: 'Завершена',
  failed: 'Ошибка',
  cancelled: 'Отменена',
}

const TARGET_LABELS: Record<string, string> = {
  all: 'Все пользователи',
  invite_link: 'По инвайт-ссылке',
  funnel_stage: 'По воронке',
  manual: 'Вручную',
}

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '—'
  try {
    return new Date(dateStr).toLocaleString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

/** Парсит JSONB поле, которое может прийти как строка из asyncpg */
function parseJsonField<T>(value: T | string | null | undefined): T | null {
  if (value == null) return null
  if (typeof value === 'string') {
    try { return JSON.parse(value) } catch { return null }
  }
  return value as T
}

interface Props {
  onEdit: () => void
}

export function BroadcastDetail({ onEdit }: Props) {
  const {
    currentBroadcast: broadcast,
    recipients,
    fetchRecipients,
    sendBroadcast,
    cancelBroadcast,
    deleteBroadcast,
    selectBroadcast,
    isSending,
  } = useBroadcastStore()

  // Load recipients for completed/failed broadcasts
  useEffect(() => {
    if (broadcast && (broadcast.status === 'completed' || broadcast.status === 'failed')) {
      fetchRecipients(broadcast.id)
    }
  }, [broadcast, fetchRecipients])

  if (!broadcast) return null

  const pollOptions = parseJsonField<string[]>(broadcast.poll_options)
  const inlineButtons = parseJsonField<import('@/types').BroadcastButton[]>(broadcast.inline_buttons)

  const handleSend = async () => {
    if (!confirm('Отправить рассылку сейчас?')) return
    await sendBroadcast(broadcast.id)
  }

  const handleCancel = async () => {
    if (!confirm('Отменить запланированную рассылку?')) return
    await cancelBroadcast(broadcast.id)
  }

  const handleDelete = async () => {
    if (!confirm(`Удалить рассылку "${broadcast.title}"?`)) return
    await deleteBroadcast(broadcast.id)
    selectBroadcast(null)
  }

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <h3 className={styles.title}>{broadcast.title || 'Без названия'}</h3>
        <span className={`${styles.badge} ${styles[`badge_${broadcast.status}`]}`}>
          {STATUS_LABELS[broadcast.status]}
        </span>
      </div>

      {/* Sending progress */}
      {broadcast.status === 'sending' && (
        <BroadcastProgress broadcast={broadcast} />
      )}

      {/* Info grid */}
      <div className={styles.infoGrid}>
        <div className={styles.infoItem}>
          <span className={styles.infoLabel}>Аудитория</span>
          <span className={styles.infoValue}>{TARGET_LABELS[broadcast.target_type]}</span>
        </div>
        <div className={styles.infoItem}>
          <span className={styles.infoLabel}>Получателей</span>
          <span className={styles.infoValue}>{broadcast.total_recipients}</span>
        </div>
        <div className={styles.infoItem}>
          <span className={styles.infoLabel}>Создана</span>
          <span className={styles.infoValue}>{formatDateTime(broadcast.created_at)}</span>
        </div>
        {broadcast.scheduled_at && (
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>Запланирована на</span>
            <span className={styles.infoValue}>{formatDateTime(broadcast.scheduled_at)}</span>
          </div>
        )}
        {broadcast.started_at && (
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>Начата</span>
            <span className={styles.infoValue}>{formatDateTime(broadcast.started_at)}</span>
          </div>
        )}
        {broadcast.completed_at && (
          <div className={styles.infoItem}>
            <span className={styles.infoLabel}>Завершена</span>
            <span className={styles.infoValue}>{formatDateTime(broadcast.completed_at)}</span>
          </div>
        )}
      </div>

      {/* Results for completed/failed */}
      {(broadcast.status === 'completed' || broadcast.status === 'failed') && (
        <div className={styles.resultsSection}>
          <h4 className={styles.sectionTitle}>Результаты</h4>
          <div className={styles.resultCards}>
            <div className={`${styles.resultCard} ${styles.resultCardSent}`}>
              <span className={styles.resultValue}>{broadcast.sent_count}</span>
              <span className={styles.resultLabel}>Доставлено</span>
            </div>
            <div className={`${styles.resultCard} ${styles.resultCardFailed}`}>
              <span className={styles.resultValue}>{broadcast.failed_count}</span>
              <span className={styles.resultLabel}>Ошибок</span>
            </div>
            <div className={styles.resultCard}>
              <span className={styles.resultValue}>{broadcast.total_recipients}</span>
              <span className={styles.resultLabel}>Всего</span>
            </div>
          </div>
        </div>
      )}

      {/* Message preview */}
      {broadcast.message_text && (
        <div className={styles.previewSection}>
          <h4 className={styles.sectionTitle}>Сообщение</h4>
          <div
            className={styles.messagePreview}
            dangerouslySetInnerHTML={{ __html: broadcast.message_text }}
          />
        </div>
      )}

      {/* Inline buttons preview */}
      {inlineButtons && inlineButtons.length > 0 && (
        <div className={styles.previewSection}>
          <h4 className={styles.sectionTitle}>Кнопки</h4>
          <div className={styles.buttonsPreview}>
            {(() => {
              const rowsMap: Record<number, typeof inlineButtons> = {}
              for (const btn of inlineButtons) {
                const r = btn.row ?? 0
                if (!rowsMap[r]) rowsMap[r] = []
                rowsMap[r]!.push(btn)
              }
              return Object.keys(rowsMap).sort().map((rowKey) => (
                <div key={rowKey} className={styles.buttonsRow}>
                  {rowsMap[Number(rowKey)]!.map((btn, i) => (
                    <span key={i} className={`${styles.buttonPreview} ${btn.type === 'url' ? styles.buttonPreviewUrl : styles.buttonPreviewReply}`}>
                      {btn.type === 'url' ? '🔗 ' : ''}{btn.text}
                    </span>
                  ))}
                </div>
              ))
            })()}
          </div>
        </div>
      )}

      {/* Poll preview */}
      {broadcast.poll_question && (
        <div className={styles.previewSection}>
          <h4 className={styles.sectionTitle}>Опрос</h4>
          <div className={styles.pollPreview}>
            <div className={styles.pollQuestion}>{broadcast.poll_question}</div>
            {pollOptions?.map((opt, i) => (
              <div key={i} className={styles.pollOption}>
                <span className={styles.pollOptionDot} />
                {opt}
              </div>
            ))}
            <div className={styles.pollFlags}>
              {broadcast.poll_is_anonymous && <span>Анонимный</span>}
              {broadcast.poll_allows_multiple && <span>Множественный выбор</span>}
            </div>
          </div>
        </div>
      )}

      {/* Stats for completed broadcasts */}
      {(broadcast.status === 'completed' || broadcast.status === 'failed') && (
        <div className={styles.previewSection}>
          <BroadcastStats
            broadcastId={broadcast.id}
            isAnonymousPoll={broadcast.poll_is_anonymous}
            hasPoll={!!broadcast.poll_question}
            hasButtons={!!inlineButtons && inlineButtons.length > 0}
          />
        </div>
      )}

      {/* Recipients list for completed/failed */}
      {(broadcast.status === 'completed' || broadcast.status === 'failed') && recipients.length > 0 && (
        <div className={styles.recipientsSection}>
          <h4 className={styles.sectionTitle}>
            Получатели ({recipients.length})
          </h4>
          <div className={styles.recipientsList}>
            {recipients.map((r) => (
              <div key={r.id} className={styles.recipientRow}>
                <span className={styles.recipientName}>
                  {r.first_name || r.username || `ID: ${r.telegram_user_id}`}
                  {r.username && <span className={styles.recipientHandle}> @{r.username}</span>}
                </span>
                <span className={`${styles.recipientStatus} ${styles[`recipientStatus_${r.status}`]}`}>
                  {r.status === 'sent' ? 'Доставлено' : r.status === 'failed' ? 'Ошибка' : 'Ожидает'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className={styles.actions}>
        {broadcast.status === 'draft' && (
          <>
            <button className={styles.editBtn} onClick={onEdit}>
              Редактировать
            </button>
            <button
              className={styles.sendBtn}
              onClick={handleSend}
              disabled={isSending}
            >
              {isSending ? 'Отправка...' : 'Отправить'}
            </button>
          </>
        )}
        {broadcast.status === 'scheduled' && (
          <button className={styles.cancelBtn} onClick={handleCancel}>
            Отменить рассылку
          </button>
        )}
        {(broadcast.status === 'draft' || broadcast.status === 'cancelled' || broadcast.status === 'completed' || broadcast.status === 'failed') && (
          <button className={styles.deleteBtn} onClick={handleDelete}>
            Удалить
          </button>
        )}
      </div>
    </div>
  )
}
