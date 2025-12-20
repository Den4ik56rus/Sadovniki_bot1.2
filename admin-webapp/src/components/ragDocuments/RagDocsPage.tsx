// RAG Documents Page — Главная страница
import { useEffect, useRef, useState, useCallback } from 'react'
import { useRagDocumentStore } from '@/store/ragDocumentStore'
import { useDocumentsStore } from '@/store'
import { RagDocumentList } from './RagDocumentList'
import { ChunkPassportEditor } from './ChunkPassportEditor'
import styles from './RagDocsPage.module.css'

export function RagDocsPage() {
  const { isEditorOpen, fetchDocuments, fetchPassportOptions } = useRagDocumentStore()
  const { subcategories, isUploading, uploadError, uploadDocument, fetchDocuments: fetchDocsStore } = useDocumentsStore()

  const [selectedCategory, setSelectedCategory] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetchDocuments()
    fetchPassportOptions()
    fetchDocsStore() // Для получения subcategories
  }, [fetchDocuments, fetchPassportOptions, fetchDocsStore])

  // Set default category when subcategories load
  useEffect(() => {
    if (subcategories.length > 0 && !selectedCategory) {
      setSelectedCategory(subcategories[0])
    }
  }, [subcategories, selectedCategory])

  const handleFile = useCallback(
    async (file: File) => {
      setLocalError(null)

      const allowedExtensions = ['.pdf', '.txt', '.md', '.docx', '.doc', '.pages']
      const fileExt = file.name.toLowerCase().slice(file.name.lastIndexOf('.'))
      if (!allowedExtensions.includes(fileExt)) {
        setLocalError('Поддерживаемые форматы: PDF, TXT, MD, DOCX, DOC, PAGES')
        return
      }

      if (!selectedCategory) {
        setLocalError('Выберите культуру')
        return
      }

      await uploadDocument(file, selectedCategory)
      // После загрузки обновляем список RAG документов
      setTimeout(() => fetchDocuments(), 1000)
    },
    [selectedCategory, uploadDocument, fetchDocuments]
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(false)

      const file = e.dataTransfer.files[0]
      if (file) {
        handleFile(file)
      }
    },
    [handleFile]
  )

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) {
        handleFile(file)
      }
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    },
    [handleFile]
  )

  const handleDropzoneClick = () => {
    fileInputRef.current?.click()
  }

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

      {/* Upload section */}
      <div className={styles.uploadSection}>
        <div className={styles.categorySelector}>
          <label htmlFor="category">Культура:</label>
          <select
            id="category"
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className={styles.select}
          >
            {subcategories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        <div
          className={`${styles.dropzone} ${isDragging ? styles.dragging : ''} ${isUploading ? styles.uploading : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={handleDropzoneClick}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md,.docx,.doc,.pages"
            onChange={handleFileSelect}
            className={styles.fileInput}
          />
          {isUploading ? (
            <div className={styles.dropzoneContent}>
              <div className={styles.spinner} />
              <p>Загрузка и обработка...</p>
            </div>
          ) : (
            <div className={styles.dropzoneContent}>
              <div className={styles.dropzoneIcon}>📄</div>
              <p className={styles.dropzoneText}>
                Перетащите файл сюда или нажмите для выбора
              </p>
              <span className={styles.dropzoneHint}>PDF, DOC, DOCX, TXT, MD, PAGES</span>
            </div>
          )}
        </div>

        {(localError || uploadError) && (
          <div className={styles.uploadError}>{localError || uploadError}</div>
        )}
      </div>

      <RagDocumentList />
    </div>
  )
}
