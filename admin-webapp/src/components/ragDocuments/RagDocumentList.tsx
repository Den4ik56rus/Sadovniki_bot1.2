// RAG Document List — Таблица документов
import { useRagDocumentStore } from '@/store/ragDocumentStore'
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

function StatusBadge({ status }: { status: string }) {
  const statusMap: Record<string, { label: string; className: string }> = {
    completed: { label: 'Готов', className: styles.statusCompleted },
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

function DocumentRow({ doc }: { doc: RagDocument }) {
  const { openEditor, deleteDocument } = useRagDocumentStore()

  const handleEdit = () => {
    if (doc.status === 'completed' && doc.chunks_count > 0) {
      openEditor(doc.id)
    }
  }

  const handleDelete = async () => {
    if (confirm(`Удалить документ "${doc.filename}"?`)) {
      await deleteDocument(doc.id)
    }
  }

  return (
    <tr className={styles.row}>
      <td className={styles.cellName}>
        <span className={styles.filename}>{doc.filename}</span>
        {doc.subcategory && (
          <span className={styles.subcategory}>{doc.subcategory}</span>
        )}
      </td>
      <td className={styles.cellStatus}>
        <StatusBadge status={doc.status} />
      </td>
      <td className={styles.cellProgress}>
        {doc.status === 'completed' && doc.chunks_count > 0 ? (
          <ProgressBar current={doc.passported_chunks} total={doc.chunks_count} />
        ) : (
          <span className={styles.noChunks}>—</span>
        )}
      </td>
      <td className={styles.cellSize}>
        {formatBytes(doc.file_size)}
      </td>
      <td className={styles.cellCost}>
        {doc.context_cost > 0 ? `$${doc.context_cost.toFixed(4)}` : '—'}
      </td>
      <td className={styles.cellDate}>
        {formatDate(doc.created_at)}
      </td>
      <td className={styles.cellActions}>
        {doc.status === 'completed' && doc.chunks_count > 0 && (
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
              <th>Контекст $</th>
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
