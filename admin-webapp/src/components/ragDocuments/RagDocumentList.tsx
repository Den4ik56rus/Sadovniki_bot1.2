// RAG Document List — Таблица документов
import { useState, useEffect } from 'react'
import { useRagDocumentStore } from '@/store/ragDocumentStore'
import { useCurrencyStore } from '@/store'
import type { RagDocument } from '@/types'
import styles from './RagDocumentList.module.css'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function StatusBadge({ status, isEmbedded }: { status: string; isEmbedded: boolean }) {
  // Двухэтапная обработка: chunked (паспортизация) → completed (в библиотеке)
  const statusMap: Record<string, { label: string; className: string }> = {
    completed: { label: isEmbedded ? 'В библиотеке' : 'Готов', className: isEmbedded ? styles.statusCompleted : styles.statusChunked },
    chunked: { label: 'Ожидает загрузки', className: styles.statusChunked },
    processing: { label: 'Обработка...', className: styles.statusProcessing },
    pending: { label: 'Ожидание', className: styles.statusPending },
    failed: { label: 'Ошибка', className: styles.statusFailed },
  }

  const info = statusMap[status] || { label: status, className: '' }

  return <span className={`${styles.status} ${info.className}`}>{info.label}</span>
}

function ProgressBar({ current, total }: { current: number; total: number }) {
  const percent = total > 0 ? Math.round((current / total) * 100) : 0

  return (
    <div className={styles.progressContainer}>
      <div className={styles.progressBar}>
        <div
          className={styles.progressFill}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className={styles.progressText}>
        {current}/{total}
      </span>
    </div>
  )
}

function CostCell({ doc }: { doc: RagDocument }) {
  const { usdRate } = useCurrencyStore()
  const [showTooltip, setShowTooltip] = useState(false)

  const chunkingCost = doc.chunking_cost || 0
  const embeddingCost = doc.embedding_cost || 0
  const contextCost = doc.context_cost || 0
  const totalCost = doc.total_cost || (chunkingCost + embeddingCost + contextCost)

  if (!totalCost || totalCost <= 0 || isNaN(totalCost)) {
    return <span className={styles.noCost}>—</span>
  }

  const totalRub = totalCost * usdRate
  const chunkingRub = chunkingCost * usdRate
  const embeddingRub = embeddingCost * usdRate
  const contextRub = contextCost * usdRate

  // Форматирование цены в рублях
  const formatRub = (rub: number) => {
    if (rub < 1) {
      return `${(rub * 100).toFixed(1)} коп.`
    }
    return `${rub.toFixed(2)} ₽`
  }

  return (
    <div
      className={styles.costWrapper}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <span className={styles.costValue}>{formatRub(totalRub)}</span>
      {showTooltip && (
        <div className={styles.costTooltip}>
          {chunkingCost > 0 && (
            <div className={styles.costTooltipRow}>
              <span>Разбивка (768d):</span>
              <span>{formatRub(chunkingRub)}</span>
            </div>
          )}
          {embeddingCost > 0 && (
            <div className={styles.costTooltipRow}>
              <span>Embeddings (3072d):</span>
              <span>{formatRub(embeddingRub)}</span>
            </div>
          )}
          <div className={styles.costTooltipRow}>
            <span>Контекст (LLM):</span>
            <span>{formatRub(contextRub)}</span>
          </div>
          <div className={styles.costTooltipDivider} />
          <div className={styles.costTooltipRow}>
            <span>Итого:</span>
            <strong>{formatRub(totalRub)}</strong>
          </div>
          <div className={styles.costTooltipUsd}>
            ${totalCost.toFixed(4)} × {usdRate.toFixed(0)} ₽/$
          </div>
        </div>
      )}
    </div>
  )
}

function DocumentRow({ doc }: { doc: RagDocument }) {
  const { openEditor, deleteDocument, embedDocument, isEmbedding } = useRagDocumentStore()

  const handleEdit = () => {
    // Разрешаем редактирование для chunked и completed
    if ((doc.status === 'completed' || doc.status === 'chunked') && doc.chunks_count > 0) {
      openEditor(doc.id)
    }
  }

  const handleDelete = async () => {
    if (confirm(`Удалить документ "${doc.filename}"?`)) {
      await deleteDocument(doc.id)
    }
  }

  const handleEmbed = async () => {
    if (confirm(`Загрузить документ "${doc.filename}" в библиотеку?\n\nЭто сгенерирует embeddings для всех чанков.`)) {
      await embedDocument(doc.id)
    }
  }

  // Условия для кнопки "Загрузить в библиотеку"
  const canEmbed = !doc.is_embedded &&
    (doc.status === 'chunked' || doc.status === 'completed') &&
    doc.chunks_count > 0 &&
    doc.passported_chunks === doc.chunks_count

  // Условия для кнопки "Паспорта"
  const canEdit = (doc.status === 'completed' || doc.status === 'chunked') && doc.chunks_count > 0

  return (
    <tr className={styles.row}>
      <td className={styles.cellName}>
        <span className={styles.filename}>{doc.filename}</span>
        {doc.subcategory && (
          <span className={styles.subcategory}>{doc.subcategory}</span>
        )}
      </td>
      <td className={styles.cellStatus}>
        <StatusBadge status={doc.status} isEmbedded={doc.is_embedded} />
      </td>
      <td className={styles.cellProgress}>
        {canEdit ? (
          <ProgressBar current={doc.passported_chunks} total={doc.chunks_count} />
        ) : (
          <span className={styles.noChunks}>—</span>
        )}
      </td>
      <td className={styles.cellSize}>
        {formatBytes(doc.file_size)}
      </td>
      <td className={styles.cellCost}>
        <CostCell doc={doc} />
      </td>
      <td className={styles.cellDate}>
        {formatDate(doc.created_at)}
      </td>
      <td className={styles.cellActions}>
        {canEmbed && (
          <button
            className={styles.btnEmbed}
            onClick={handleEmbed}
            disabled={isEmbedding}
            title="Загрузить в библиотеку"
          >
            {isEmbedding ? 'Загрузка...' : 'В библиотеку'}
          </button>
        )}
        {canEdit && (
          <button
            className={styles.btnEdit}
            onClick={handleEdit}
            title="Редактировать паспорта"
          >
            Паспорта
          </button>
        )}
        <button
          className={styles.btnDelete}
          onClick={handleDelete}
          title="Удалить документ"
        >
          Удалить
        </button>
      </td>
    </tr>
  )
}

export function RagDocumentList() {
  const { documents, isLoading, error, fetchDocuments, clearAllDocuments } = useRagDocumentStore()
  const { fetchRate } = useCurrencyStore()

  // Загрузка курса валют
  useEffect(() => {
    fetchRate()
  }, [fetchRate])

  const handleClearAll = async () => {
    if (confirm('Удалить ВСЕ RAG документы? Это действие нельзя отменить.')) {
      await clearAllDocuments()
    }
  }

  if (isLoading) {
    return (
      <div className={styles.loading}>
        Загрузка документов...
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.error}>
        <p>Ошибка: {error}</p>
        <button onClick={fetchDocuments}>Повторить</button>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div className={styles.toolbar}>
        <span className={styles.count}>
          Документов: {documents.length}
        </span>
        {documents.length > 0 && (
          <button className={styles.btnClearAll} onClick={handleClearAll}>
            Очистить все
          </button>
        )}
      </div>

      {documents.length === 0 ? (
        <div className={styles.empty}>
          <p>Нет загруженных документов</p>
          <p className={styles.emptyHint}>
            Загрузите документы через секцию "Загрузка документов"
          </p>
        </div>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Документ</th>
              <th>Статус</th>
              <th>Паспортизация</th>
              <th>Размер</th>
              <th>Стоимость</th>
              <th>Дата</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {documents.map(doc => (
              <DocumentRow key={doc.id} doc={doc} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
