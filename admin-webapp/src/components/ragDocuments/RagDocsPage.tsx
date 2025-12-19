// RAG Documents Page — Главная страница
import { useEffect } from 'react'
import { useRagDocumentStore } from '@/store/ragDocumentStore'
import { RagDocumentList } from './RagDocumentList'
import { ChunkPassportEditor } from './ChunkPassportEditor'
import styles from './RagDocsPage.module.css'

export function RagDocsPage() {
  const { isEditorOpen, fetchDocuments, fetchPassportOptions } = useRagDocumentStore()

  useEffect(() => {
    fetchDocuments()
    fetchPassportOptions()
  }, [fetchDocuments, fetchPassportOptions])

  if (isEditorOpen) {
    return <ChunkPassportEditor />
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>RAG Документы</h1>
        <p className={styles.subtitle}>
          Загрузка документов и паспортизация чанков для RAG-системы
        </p>
      </header>

      <RagDocumentList />
    </div>
  )
}
