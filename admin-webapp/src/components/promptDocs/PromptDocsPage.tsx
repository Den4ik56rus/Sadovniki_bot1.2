// Главная страница управления промт-документами

import { useEffect } from 'react'
import { usePromptDocumentStore } from '@/store/promptDocumentStore'
import { PromptDocsFilters } from './PromptDocsFilters'
import { PromptDocsList } from './PromptDocsList'
import { PromptDocUpload } from './PromptDocUpload'
import { PromptDocPreview } from './PromptDocPreview'
import styles from './PromptDocsPage.module.css'

export function PromptDocsPage() {
  const {
    fetchCultures,
    fetchWorkTypes,
    fetchDocuments,
    openUploadModal,
    isUploadModalOpen,
    isPreviewModalOpen,
    error,
    clearError,
  } = usePromptDocumentStore()

  // Загружаем данные при монтировании
  useEffect(() => {
    fetchCultures()
    fetchWorkTypes()
    fetchDocuments()
  }, [fetchCultures, fetchWorkTypes, fetchDocuments])

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}>Промт-документы</h1>
          <p className={styles.subtitle}>
            Документы для добавления в системные промпты по категориям
          </p>
        </div>
        <button className={styles.uploadBtn} onClick={openUploadModal}>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 4V16M4 10H16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          Загрузить документ
        </button>
      </div>

      {/* Error message */}
      {error && (
        <div className={styles.error}>
          <span>{error}</span>
          <button onClick={clearError} className={styles.errorClose}>×</button>
        </div>
      )}

      {/* Filters */}
      <PromptDocsFilters />

      {/* Documents list */}
      <PromptDocsList />

      {/* Upload modal */}
      {isUploadModalOpen && <PromptDocUpload />}

      {/* Preview modal */}
      {isPreviewModalOpen && <PromptDocPreview />}
    </div>
  )
}
