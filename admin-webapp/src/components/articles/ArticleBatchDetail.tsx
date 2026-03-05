// ArticleBatchDetail — progress + results view for article batch
import { useEffect, useCallback } from 'react'
import { useArticleBatchStore } from '@/store/articleBatchStore'
import { useSSE } from '@/hooks/useSSE'
import type { ArticleBatchItem, ArticleBatchProgressEvent } from '@/types'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './ArticleBatchDetail.module.css'

const API_BASE = import.meta.env.VITE_API_URL || '/api/admin'

interface Props {
  batchId: number
  onBack: () => void
  onArticleClick: (articleId: number) => void
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  try {
    return format(new Date(dateStr), 'd MMM yyyy, HH:mm', { locale: ru })
  } catch {
    return '—'
  }
}

function itemStatusIcon(status: string): string {
  switch (status) {
    case 'pending': return '\u23f3'
    case 'generating': return '\ud83d\udd04'
    case 'completed': return '\u2705'
    case 'failed': return '\u274c'
    case 'skipped': return '\u23ed\ufe0f'
    default: return '\u2753'
  }
}

function batchStatusLabel(status: string): string {
  switch (status) {
    case 'pending': return 'Ожидание'
    case 'running': return 'Генерация...'
    case 'completed': return 'Завершён'
    case 'cancelled': return 'Отменён'
    default: return status
  }
}

function batchStatusClass(status: string): string {
  switch (status) {
    case 'running': return styles.statusRunning
    case 'completed': return styles.statusCompleted
    case 'cancelled': return styles.statusCancelled
    case 'pending': return styles.statusPending
    default: return ''
  }
}

export function ArticleBatchDetail({ batchId, onBack, onArticleClick }: Props) {
  const currentBatch = useArticleBatchStore(s => s.currentBatch)
  const progressEvent = useArticleBatchStore(s => s.progressEvent)
  const fetchBatch = useArticleBatchStore(s => s.fetchBatch)
  const cancelBatch = useArticleBatchStore(s => s.cancelBatch)
  const clearCurrentBatch = useArticleBatchStore(s => s.clearCurrentBatch)
  const setProgressEvent = useArticleBatchStore(s => s.setProgressEvent)

  // Load batch
  useEffect(() => {
    fetchBatch(batchId)
    return () => { clearCurrentBatch() }
  }, [batchId])

  // SSE for progress
  const handleSSEMessage = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data) as ArticleBatchProgressEvent
      setProgressEvent(data)

      if (data.type === 'article_batch_item_completed' || data.type === 'article_batch_item_failed' || data.type === 'article_batch_completed' || data.type === 'article_batch_cancelled') {
        fetchBatch(batchId)
      }
    } catch { /* ignore parse errors */ }
  }, [batchId, fetchBatch, setProgressEvent])

  useSSE({
    endpoint: `${API_BASE.replace('/api/admin', '')}/api/admin/events/article-batch/${batchId}`,
    onMessage: handleSSEMessage,
    enabled: currentBatch?.status === 'running' || currentBatch?.status === 'pending',
  })

  if (!currentBatch) {
    return (
      <div>
        <button className={styles.backButton} onClick={onBack}>&larr; Назад</button>
        <div className={styles.loading}>Загрузка...</div>
      </div>
    )
  }

  const batch = currentBatch
  const items = batch.items || []
  const isRunning = batch.status === 'running'
  const successPct = batch.total_items > 0 ? (batch.completed_items / batch.total_items) * 100 : 0
  const failPct = batch.total_items > 0 ? (batch.failed_items / batch.total_items) * 100 : 0

  // Current item info from progress event
  let currentInfo = ''
  if (progressEvent && progressEvent.type === 'article_batch_item_started') {
    currentInfo = progressEvent.topic || ''
  }

  return (
    <div>
      <button className={styles.backButton} onClick={onBack}>&larr; Назад</button>

      <div className={styles.header}>
        <h2 className={styles.title}>
          Пакет статей #{batch.id}
          <span className={`${styles.batchStatus} ${batchStatusClass(batch.status)}`}>
            {batchStatusLabel(batch.status)}
          </span>
        </h2>
        <p className={styles.subtitle}>
          Создан: {formatDate(batch.created_at)}
          {batch.finished_at && ` | Завершён: ${formatDate(batch.finished_at)}`}
          {batch.total_cost_usd > 0 && ` | Стоимость: $${batch.total_cost_usd.toFixed(2)}`}
        </p>
      </div>

      {/* Progress */}
      <div className={styles.progressSection}>
        <div className={styles.progressHeader}>
          <span className={styles.progressTitle}>
            Прогресс: {batch.completed_items + batch.failed_items}/{batch.total_items}
          </span>
          {isRunning && (
            <button className={styles.cancelButton} onClick={() => cancelBatch(batch.id)}>
              Отменить
            </button>
          )}
        </div>

        <div className={styles.progressBar}>
          <div
            className={`${styles.progressFill} ${styles.progressFillSuccess}`}
            style={{ width: `${successPct}%`, display: 'inline-block' }}
          />
          <div
            className={`${styles.progressFill} ${styles.progressFillError}`}
            style={{ width: `${failPct}%`, display: 'inline-block' }}
          />
        </div>

        <div className={styles.progressStats}>
          <span>&#9989; Готово: {batch.completed_items}</span>
          <span>&#10060; Ошибки: {batch.failed_items}</span>
          <span>&#9203; Ожидание: {batch.total_items - batch.completed_items - batch.failed_items - items.filter(i => i.status === 'skipped').length}</span>
        </div>

        {currentInfo && isRunning && (
          <div className={styles.currentItem}>
            &#9997; {currentInfo}
          </div>
        )}

        {/* Items list */}
        <div className={styles.itemsList}>
          {items.map((item: ArticleBatchItem) => (
            <div key={item.id} className={styles.item}>
              <span className={styles.itemStatus}>{itemStatusIcon(item.status)}</span>
              <span className={styles.itemTitle}>{item.topic}</span>
              {item.article_id && (
                <span
                  className={styles.itemLink}
                  onClick={() => onArticleClick(item.article_id!)}
                >
                  &#128196; Открыть
                </span>
              )}
              {item.error_message && (
                <span className={styles.itemError} title={item.error_message}>
                  {item.error_message}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
