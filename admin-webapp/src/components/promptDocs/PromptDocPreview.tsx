// Модальное окно просмотра содержимого документа

import { usePromptDocumentStore } from '@/store/promptDocumentStore'
import styles from './PromptDocPreview.module.css'

export function PromptDocPreview() {
  const {
    selectedDocument,
    documentContent,
    closePreviewModal,
  } = usePromptDocumentStore()

  if (!selectedDocument) return null

  return (
    <div className={styles.overlay} onClick={closePreviewModal}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.headerInfo}>
            <h2 className={styles.title}>{selectedDocument.original_filename}</h2>
            <div className={styles.meta}>
              <span className={styles.badge}>{selectedDocument.culture_name}</span>
              {selectedDocument.subculture_name && (
                <span className={styles.badgeSecondary}>{selectedDocument.subculture_name}</span>
              )}
              <span className={styles.badgeWork}>{selectedDocument.work_type_name}</span>
            </div>
          </div>
          <button className={styles.closeBtn} onClick={closePreviewModal}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M5 5L15 15M5 15L15 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        <div className={styles.content}>
          {documentContent === null ? (
            <div className={styles.loading}>
              <div className={styles.spinner} />
              <span>Загрузка содержимого...</span>
            </div>
          ) : documentContent === '' ? (
            <div className={styles.empty}>
              <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                <path d="M24 20V28M24 34V34.01" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
                <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="2"/>
              </svg>
              <p>Не удалось загрузить содержимое документа</p>
            </div>
          ) : (
            <pre className={styles.text}>{documentContent}</pre>
          )}
        </div>

        <div className={styles.footer}>
          <button className={styles.closeFooterBtn} onClick={closePreviewModal}>
            Закрыть
          </button>
        </div>
      </div>
    </div>
  )
}
