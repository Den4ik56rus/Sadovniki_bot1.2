// Список промт-документов

import { useRef } from 'react'
import { usePromptDocumentStore } from '@/store/promptDocumentStore'
import type { PromptDocument } from '@/types'
import styles from './PromptDocsList.module.css'

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'completed':
      return { text: 'Готов', className: styles.statusCompleted }
    case 'pending':
      return { text: 'Обработка...', className: styles.statusPending }
    case 'failed':
      return { text: 'Ошибка', className: styles.statusFailed }
    default:
      return { text: status, className: '' }
  }
}

function getFileTypeIcon(fileType: string) {
  switch (fileType) {
    case 'pdf':
      return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className={styles.iconPdf}>
          <path d="M14 2H6C4.89543 2 4 2.89543 4 4V20C4 21.1046 4.89543 22 6 22H18C19.1046 22 20 21.1046 20 20V8L14 2Z" stroke="currentColor" strokeWidth="2"/>
          <path d="M14 2V8H20" stroke="currentColor" strokeWidth="2"/>
          <text x="12" y="16" textAnchor="middle" fontSize="6" fill="currentColor">PDF</text>
        </svg>
      )
    case 'docx':
      return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className={styles.iconDocx}>
          <path d="M14 2H6C4.89543 2 4 2.89543 4 4V20C4 21.1046 4.89543 22 6 22H18C19.1046 22 20 21.1046 20 20V8L14 2Z" stroke="currentColor" strokeWidth="2"/>
          <path d="M14 2V8H20" stroke="currentColor" strokeWidth="2"/>
          <text x="12" y="16" textAnchor="middle" fontSize="5" fill="currentColor">DOC</text>
        </svg>
      )
    case 'pages':
      return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className={styles.iconPages}>
          <path d="M14 2H6C4.89543 2 4 2.89543 4 4V20C4 21.1046 4.89543 22 6 22H18C19.1046 22 20 21.1046 20 20V8L14 2Z" stroke="currentColor" strokeWidth="2"/>
          <path d="M14 2V8H20" stroke="currentColor" strokeWidth="2"/>
          <circle cx="12" cy="14" r="3" stroke="currentColor" strokeWidth="1.5"/>
        </svg>
      )
    default:
      return (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className={styles.iconDefault}>
          <path d="M14 2H6C4.89543 2 4 2.89543 4 4V20C4 21.1046 4.89543 22 6 22H18C19.1046 22 20 21.1046 20 20V8L14 2Z" stroke="currentColor" strokeWidth="2"/>
          <path d="M14 2V8H20" stroke="currentColor" strokeWidth="2"/>
        </svg>
      )
  }
}

interface DocumentRowProps {
  doc: PromptDocument
  onPreview: (doc: PromptDocument) => void
  onDelete: (id: number) => void
  onReplace: (id: number, file: File) => void
}

function DocumentRow({ doc, onPreview, onDelete, onReplace }: DocumentRowProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const status = getStatusBadge(doc.extraction_status)

  const handleReplaceClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      onReplace(doc.id, file)
    }
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <tr className={styles.row}>
      <td className={styles.cellIcon}>
        {getFileTypeIcon(doc.file_type)}
      </td>
      <td className={styles.cellName}>
        <div className={styles.fileName}>{doc.original_filename}</div>
        <div className={styles.fileMeta}>
          {formatFileSize(doc.file_size)} • {doc.file_type.toUpperCase()}
        </div>
      </td>
      <td className={styles.cellCategory}>
        <span className={styles.badge}>{doc.culture_name}</span>
        {doc.subculture_name && (
          <span className={styles.badgeSecondary}>{doc.subculture_name}</span>
        )}
      </td>
      <td className={styles.cellWorkType}>
        <span className={styles.badgeWork}>{doc.work_type_name}</span>
      </td>
      <td className={styles.cellStatus}>
        <span className={`${styles.status} ${status.className}`}>
          {status.text}
        </span>
        {doc.extraction_error && (
          <span className={styles.errorHint} title={doc.extraction_error}>!</span>
        )}
      </td>
      <td className={styles.cellDate}>
        {formatDate(doc.created_at)}
      </td>
      <td className={styles.cellActions}>
        <button
          className={styles.actionBtn}
          onClick={() => onPreview(doc)}
          disabled={doc.extraction_status !== 'completed'}
          title="Просмотреть"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M1 9C1 9 4 3 9 3C14 3 17 9 17 9C17 9 14 15 9 15C4 15 1 9 1 9Z" stroke="currentColor" strokeWidth="1.5"/>
            <circle cx="9" cy="9" r="2.5" stroke="currentColor" strokeWidth="1.5"/>
          </svg>
        </button>
        <button
          className={styles.actionBtn}
          onClick={handleReplaceClick}
          title="Заменить"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M14 6L16 4L14 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M2 9C2 5.13401 5.13401 2 9 2H16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M4 12L2 14L4 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M16 9C16 12.866 12.866 16 9 16H2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
        <button
          className={`${styles.actionBtn} ${styles.actionDelete}`}
          onClick={() => onDelete(doc.id)}
          title="Удалить"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M3 5H15M6 5V3H12V5M7 8V13M11 8V13M4 5L5 15H13L14 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pages,.docx,.pdf"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
      </td>
    </tr>
  )
}

export function PromptDocsList() {
  const {
    documents,
    total,
    isLoading,
    openPreviewModal,
    deleteDocument,
    replaceDocument,
  } = usePromptDocumentStore()

  const handleDelete = async (id: number) => {
    if (confirm('Удалить этот документ?')) {
      await deleteDocument(id)
    }
  }

  const handleReplace = async (id: number, file: File) => {
    await replaceDocument(id, file)
  }

  if (isLoading) {
    return (
      <div className={styles.loading}>
        <div className={styles.spinner} />
        <span>Загрузка документов...</span>
      </div>
    )
  }

  if (documents.length === 0) {
    return (
      <div className={styles.empty}>
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
          <path d="M28 4H12C9.79086 4 8 5.79086 8 8V40C8 42.2091 9.79086 44 12 44H36C38.2091 44 40 42.2091 40 40V16L28 4Z" stroke="currentColor" strokeWidth="2"/>
          <path d="M28 4V16H40" stroke="currentColor" strokeWidth="2"/>
          <path d="M18 26H30M18 34H26" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        </svg>
        <p>Документы не найдены</p>
        <span>Загрузите первый документ или измените фильтры</span>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div className={styles.tableHeader}>
        <span className={styles.count}>{total} документ{total === 1 ? '' : total < 5 ? 'а' : 'ов'}</span>
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th></th>
            <th>Файл</th>
            <th>Культура</th>
            <th>Тип работ</th>
            <th>Статус</th>
            <th>Загружен</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => (
            <DocumentRow
              key={doc.id}
              doc={doc}
              onPreview={openPreviewModal}
              onDelete={handleDelete}
              onReplace={handleReplace}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
