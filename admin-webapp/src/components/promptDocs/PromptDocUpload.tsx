// Модальное окно загрузки промт-документа

import { useState, useCallback, useRef } from 'react'
import { usePromptDocumentStore } from '@/store/promptDocumentStore'
import styles from './PromptDocUpload.module.css'

export function PromptDocUpload() {
  const {
    cultures,
    subcultures,
    workTypes,
    isUploading,
    error,
    closeUploadModal,
    uploadDocument,
    fetchSubcultures,
  } = usePromptDocumentStore()

  const [file, setFile] = useState<File | null>(null)
  const [cultureId, setCultureId] = useState<number | null>(null)
  const [subcultureId, setSubcultureId] = useState<number | null>(null)
  const [workTypeId, setWorkTypeId] = useState<number | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleCultureChange = useCallback((id: number | null) => {
    setCultureId(id)
    setSubcultureId(null)
    if (id) {
      fetchSubcultures(id)
    }
  }, [fetchSubcultures])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile && isValidFile(droppedFile)) {
      setFile(droppedFile)
    }
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile && isValidFile(selectedFile)) {
      setFile(selectedFile)
    }
  }, [])

  const isValidFile = (file: File): boolean => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    return ['pages', 'docx', 'pdf'].includes(ext || '')
  }

  const handleSubmit = async () => {
    if (!file || !cultureId || !workTypeId) return

    const success = await uploadDocument(file, cultureId, subcultureId, workTypeId)
    if (success) {
      closeUploadModal()
    }
  }

  const canSubmit = file && cultureId && workTypeId && !isUploading

  // Check if selected culture has subcultures
  const hasSubcultures = cultureId && subcultures.length > 0

  return (
    <div className={styles.overlay} onClick={closeUploadModal}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.title}>Загрузить документ</h2>
          <button className={styles.closeBtn} onClick={closeUploadModal}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M5 5L15 15M5 15L15 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        <div className={styles.content}>
          {/* Drop zone */}
          <div
            className={`${styles.dropzone} ${isDragging ? styles.dropzoneDragging : ''} ${file ? styles.dropzoneHasFile : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            {file ? (
              <div className={styles.selectedFile}>
                <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                  <path d="M18 4H10C7.79086 4 6 5.79086 6 8V24C6 26.2091 7.79086 28 10 28H22C24.2091 28 26 26.2091 26 24V12L18 4Z" stroke="currentColor" strokeWidth="2"/>
                  <path d="M18 4V12H26" stroke="currentColor" strokeWidth="2"/>
                </svg>
                <div className={styles.fileInfo}>
                  <span className={styles.fileName}>{file.name}</span>
                  <span className={styles.fileSize}>
                    {(file.size / 1024).toFixed(1)} KB
                  </span>
                </div>
                <button
                  className={styles.removeFile}
                  onClick={(e) => { e.stopPropagation(); setFile(null); }}
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M4 4L12 12M4 12L12 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                </button>
              </div>
            ) : (
              <>
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none" className={styles.uploadIcon}>
                  <path d="M24 32V16M24 16L18 22M24 16L30 22" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M40 28V36C40 38.2091 38.2091 40 36 40H12C9.79086 40 8 38.2091 8 36V28" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                <p className={styles.dropText}>
                  Перетащите файл сюда или <span>выберите</span>
                </p>
                <p className={styles.dropHint}>
                  Поддерживаются: .pages, .docx, .pdf
                </p>
              </>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pages,.docx,.pdf"
              onChange={handleFileSelect}
              className={styles.fileInput}
            />
          </div>

          {/* Category selection */}
          <div className={styles.formGrid}>
            {/* Culture */}
            <div className={styles.formGroup}>
              <label className={styles.label}>Культура *</label>
              <select
                className={styles.select}
                value={cultureId || ''}
                onChange={(e) => handleCultureChange(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Выберите культуру</option>
                {cultures.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            {/* Subculture (if available) */}
            {hasSubcultures && (
              <div className={styles.formGroup}>
                <label className={styles.label}>Подкультура</label>
                <select
                  className={styles.select}
                  value={subcultureId || ''}
                  onChange={(e) => setSubcultureId(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">Без подкультуры (общая)</option>
                  {subcultures.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
            )}

            {/* Work type */}
            <div className={styles.formGroup}>
              <label className={styles.label}>Тип работ *</label>
              <select
                className={styles.select}
                value={workTypeId || ''}
                onChange={(e) => setWorkTypeId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Выберите тип работ</option>
                {workTypes.map((w) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className={styles.error}>
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <button className={styles.cancelBtn} onClick={closeUploadModal}>
            Отмена
          </button>
          <button
            className={styles.submitBtn}
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {isUploading ? (
              <>
                <span className={styles.spinner} />
                Загрузка...
              </>
            ) : (
              'Загрузить'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
