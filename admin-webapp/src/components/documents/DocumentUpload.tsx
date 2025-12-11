import { useEffect, useRef, useState, useCallback } from 'react'
import { useDocumentsStore, useCurrencyStore } from '@/store'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './DocumentUpload.module.css'

export function DocumentUpload() {
  const {
    documents,
    subcategories,
    isLoading,
    isUploading,
    error,
    uploadError,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    pollProcessingDocuments,
  } = useDocumentsStore()

  const { usdRate, fetchRate } = useCurrencyStore()

  const [selectedCategory, setSelectedCategory] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Initial fetch
  useEffect(() => {
    fetchDocuments()
    fetchRate()
  }, [fetchDocuments, fetchRate])

  // Set default category when subcategories load
  useEffect(() => {
    if (subcategories.length > 0 && !selectedCategory) {
      setSelectedCategory(subcategories[0])
    }
  }, [subcategories, selectedCategory])

  // Poll for processing documents
  useEffect(() => {
    const hasProcessing = documents.some(
      (d) => d.status === 'processing' || d.status === 'pending'
    )
    if (!hasProcessing) return

    const interval = setInterval(() => {
      pollProcessingDocuments()
    }, 3000)

    return () => clearInterval(interval)
  }, [documents, pollProcessingDocuments])

  const handleFile = useCallback(
    async (file: File) => {
      setLocalError(null)

      const allowedExtensions = ['.pdf', '.txt', '.md', '.docx', '.doc']
      const fileExt = file.name.toLowerCase().slice(file.name.lastIndexOf('.'))
      if (!allowedExtensions.includes(fileExt)) {
        setLocalError('Поддерживаемые форматы: PDF, TXT, MD, DOCX, DOC')
        return
      }

      if (!selectedCategory) {
        setLocalError('Выберите культуру')
        return
      }

      await uploadDocument(file, selectedCategory)
    },
    [selectedCategory, uploadDocument]
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
      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    },
    [handleFile]
  )

  const handleDropzoneClick = () => {
    fileInputRef.current?.click()
  }

  const handleDelete = async (id: number, filename: string) => {
    if (confirm(`Удалить документ "${filename}"?`)) {
      await deleteDocument(id)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatCost = (costUsd: number) => {
    if (costUsd === 0) return null
    const costRub = costUsd * usdRate
    // Показываем в копейках если меньше 1 рубля
    if (costRub < 1) {
      return `${(costRub * 100).toFixed(1)} коп.`
    }
    return `${costRub.toFixed(2)} ₽`
  }

  const getFileExtIcon = (filename: string) => {
    const ext = filename.toLowerCase().slice(filename.lastIndexOf('.') + 1)
    switch (ext) {
      case 'pdf':
        return 'PDF'
      case 'docx':
      case 'doc':
        return 'DOC'
      case 'txt':
        return 'TXT'
      case 'md':
        return 'MD'
      default:
        return 'DOC'
    }
  }

  const getStatusBadge = (status: string, error: string | null) => {
    switch (status) {
      case 'completed':
        return <span className={`${styles.badge} ${styles.badgeSuccess}`}>Готово</span>
      case 'processing':
        return <span className={`${styles.badge} ${styles.badgeProcessing}`}>Обработка...</span>
      case 'pending':
        return <span className={`${styles.badge} ${styles.badgePending}`}>В очереди</span>
      case 'failed':
        return (
          <span className={`${styles.badge} ${styles.badgeError}`} title={error || 'Ошибка'}>
            Ошибка
          </span>
        )
      default:
        return null
    }
  }

  if (error) {
    return <div className={styles.error}>Ошибка: {error}</div>
  }

  return (
    <div className={styles.container}>
      <h2 className={styles.title}>Загрузка документов</h2>

      {/* Category selector */}
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

      {/* Dropzone */}
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
          accept=".pdf,.txt,.md,.docx,.doc"
          onChange={handleFileSelect}
          className={styles.fileInput}
        />
        {isUploading ? (
          <div className={styles.dropzoneContent}>
            <div className={styles.spinner} />
            <p>Загрузка...</p>
          </div>
        ) : (
          <div className={styles.dropzoneContent}>
            <div className={styles.dropzoneIcon}>DOC</div>
            <p className={styles.dropzoneText}>
              Перетащите файл сюда
              <br />
              <span className={styles.dropzoneHint}>PDF, DOC, DOCX, TXT, MD — или нажмите для выбора</span>
            </p>
          </div>
        )}
      </div>

      {/* Errors */}
      {(localError || uploadError) && (
        <div className={styles.uploadError}>{localError || uploadError}</div>
      )}

      {/* Documents list */}
      <div className={styles.documentsSection}>
        <h3 className={styles.sectionTitle}>
          Загруженные документы
          {isLoading && <span className={styles.loadingText}> (загрузка...)</span>}
        </h3>

        {documents.length === 0 ? (
          <div className={styles.emptyList}>Нет загруженных документов</div>
        ) : (
          <div className={styles.documentsList}>
            {documents.map((doc) => (
              <div key={doc.id} className={styles.documentCard}>
                <div className={styles.documentMain}>
                  <div className={styles.documentIcon}>{getFileExtIcon(doc.filename)}</div>
                  <div className={styles.documentInfo}>
                    <div className={styles.documentName}>{doc.filename}</div>
                    <div className={styles.documentMeta}>
                      <span className={styles.documentCategory}>{doc.subcategory}</span>
                      <span className={styles.documentSize}>{formatFileSize(doc.file_size)}</span>
                      {doc.status === 'completed' && (
                        <>
                          <span className={styles.documentChunks}>{doc.chunks_count} чанков</span>
                          {formatCost(doc.embedding_cost_usd) && (
                            <span className={styles.documentCost}>{formatCost(doc.embedding_cost_usd)}</span>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                </div>
                <div className={styles.documentActions}>
                  {getStatusBadge(doc.status, doc.error)}
                  {doc.created_at && (
                    <span className={styles.documentDate}>
                      {format(new Date(doc.created_at), 'd MMM yyyy', { locale: ru })}
                    </span>
                  )}
                  <button
                    className={styles.deleteButton}
                    onClick={() => handleDelete(doc.id, doc.filename)}
                    title="Удалить"
                  >
                    x
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
