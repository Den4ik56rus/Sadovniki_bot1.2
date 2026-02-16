import { useState, useCallback } from 'react'
import type { PromptPreviewSection } from '@/types'
import { api } from '@/services/api'
import { PromptHistory } from '../prompts/PromptHistory'
import styles from './PromptSection.module.css'

interface Props {
  section: PromptPreviewSection
  onSaved?: () => void
}

export function PromptSection({ section, onSaved }: Props) {
  const isDisabled = section.is_enabled === false && !section.is_placeholder
  const isPlaceholder = section.is_placeholder === true
  const isEditable = !!section.prompt_id && section.is_from_db === true
  const isComposite = (section.prompt_ids?.length ?? 0) > 1

  const [isEditing, setIsEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)
  const [originalContent, setOriginalContent] = useState('')

  const handleEditClick = useCallback(async () => {
    if (!section.prompt_id) return

    try {
      // Загружаем RAW контент из API (без подстановки переменных)
      const response = await api.getPrompt(section.prompt_id)
      const raw = response.prompt.content
      setEditContent(raw)
      setOriginalContent(raw)
      setHasChanges(false)
      setIsEditing(true)
    } catch (e) {
      console.error('Error loading prompt for edit:', e)
    }
  }, [section.prompt_id])

  const handleCancel = () => {
    setIsEditing(false)
    setEditContent('')
    setHasChanges(false)
  }

  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newContent = e.target.value
    setEditContent(newContent)
    setHasChanges(newContent !== originalContent)
  }

  const handleSave = async () => {
    if (!section.prompt_id || !hasChanges) return

    setIsSaving(true)
    try {
      await api.updatePrompt(section.prompt_id, editContent, 'admin')
      setIsEditing(false)
      setHasChanges(false)
      onSaved?.()
    } catch (e) {
      console.error('Error saving prompt:', e)
    } finally {
      setIsSaving(false)
    }
  }

  const handleHistoryClose = () => {
    setShowHistory(false)
    // Перезагружаем превью после возможного revert
    onSaved?.()
  }

  return (
    <div className={`${styles.section} ${isDisabled ? styles.disabled : ''}`}>
      {/* Аннотация слева */}
      <div
        className={styles.annotation}
        style={{ borderLeftColor: section.color }}
      >
        <div className={styles.annotationDot} style={{ backgroundColor: section.color }} />
        <div className={styles.annotationLabel}>{section.label}</div>
        <div className={styles.annotationMeta}>
          {section.is_from_db !== undefined && (
            <span className={styles.sourceTag}>
              {section.is_from_db ? 'БД' : 'Python'}
            </span>
          )}
          {isDisabled && (
            <span className={styles.disabledTag}>
              {section.skipped_reason || 'Отключено'}
            </span>
          )}
          {isEditable && !isEditing && (
            <button
              className={styles.editButton}
              onClick={handleEditClick}
              title="Редактировать"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
          )}
          {isComposite && !isEditable && (
            <span className={styles.compositeTag}>
              Составная ({section.prompt_ids?.length})
            </span>
          )}
        </div>
      </div>

      {/* Контент справа */}
      <div className={styles.contentWrapper}>
        {isEditing ? (
          <div className={styles.editMode}>
            <textarea
              className={styles.editTextarea}
              value={editContent}
              onChange={handleContentChange}
              spellCheck={false}
            />
            <div className={styles.editToolbar}>
              <button
                className={styles.cancelBtn}
                onClick={handleCancel}
                disabled={isSaving}
              >
                Отмена
              </button>
              <button
                className={styles.historyBtn}
                onClick={() => setShowHistory(true)}
              >
                История
              </button>
              <button
                className={`${styles.saveBtn} ${hasChanges ? styles.hasChanges : ''}`}
                onClick={handleSave}
                disabled={!hasChanges || isSaving}
              >
                {isSaving ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          </div>
        ) : isPlaceholder ? (
          <div className={styles.placeholder}>
            <div className={styles.placeholderIcon}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3"/>
                <path d="M8 12H16M12 8V16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </div>
            <pre className={styles.placeholderText}>{section.placeholder_text}</pre>
          </div>
        ) : isDisabled ? (
          <div className={styles.disabledContent}>
            {section.content ? (
              <details className={styles.collapsible}>
                <summary>Показать содержимое (отключено)</summary>
                <pre className={styles.content}>{section.content}</pre>
              </details>
            ) : (
              <span className={styles.emptyNote}>{section.skipped_reason || 'Секция отключена'}</span>
            )}
          </div>
        ) : (
          <pre className={styles.content}>{section.content}</pre>
        )}
      </div>

      {/* История */}
      {showHistory && section.prompt_id && (
        <PromptHistory
          promptId={section.prompt_id}
          promptName={section.label}
          onClose={handleHistoryClose}
        />
      )}
    </div>
  )
}
