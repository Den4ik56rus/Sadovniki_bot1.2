/**
 * Редактор промпта.
 *
 * Отображает:
 * - Заголовок с названием промпта
 * - Textarea для редактирования content
 * - Кнопки: Сохранить, История
 * - Метаинформация (версия, дата обновления, системный)
 */

import { useState, useEffect } from 'react'
import { usePromptStore } from '@/store/promptStore'
import { PromptHistory } from './PromptHistory'
import styles from './PromptEditor.module.css'

export function PromptEditor() {
  const {
    selectedPrompt,
    isSaving,
    updatePrompt,
    togglePromptEnabled,
  } = usePromptStore()

  const [content, setContent] = useState('')
  const [hasChanges, setHasChanges] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  // Sync content when selected prompt changes
  useEffect(() => {
    if (selectedPrompt) {
      setContent(selectedPrompt.content)
      setHasChanges(false)
    } else {
      setContent('')
      setHasChanges(false)
    }
  }, [selectedPrompt])

  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newContent = e.target.value
    setContent(newContent)
    setHasChanges(newContent !== selectedPrompt?.content)
  }

  const handleSave = async () => {
    if (!selectedPrompt || !hasChanges) return
    await updatePrompt(selectedPrompt.id, content)
    setHasChanges(false)
  }

  const handleToggleEnabled = () => {
    if (!selectedPrompt) return
    togglePromptEnabled(selectedPrompt.id, !selectedPrompt.is_enabled)
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  if (!selectedPrompt) {
    return (
      <div className={styles.emptyState}>
        <div className={styles.emptyIcon}>📝</div>
        <div className={styles.emptyTitle}>Выберите промпт</div>
        <div className={styles.emptyText}>
          Выберите промпт из списка слева для редактирования
        </div>
      </div>
    )
  }

  return (
    <div className={styles.editor}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h2 className={styles.title}>{selectedPrompt.name}</h2>
          {selectedPrompt.description && (
            <p className={styles.description}>{selectedPrompt.description}</p>
          )}
        </div>
        <div className={styles.headerRight}>
          <label className={styles.enabledToggle}>
            <input
              type="checkbox"
              checked={selectedPrompt.is_enabled}
              onChange={handleToggleEnabled}
            />
            <span>Включён</span>
          </label>
        </div>
      </div>

      {/* Textarea */}
      <div className={styles.textareaWrapper}>
        <textarea
          className={styles.textarea}
          value={content}
          onChange={handleContentChange}
          placeholder="Текст промпта..."
          spellCheck={false}
        />
      </div>

      {/* Footer */}
      <div className={styles.footer}>
        <div className={styles.footerLeft}>
          <div className={styles.meta}>
            <span className={styles.version}>v{selectedPrompt.version}</span>
            <span className={styles.separator}>•</span>
            <span className={styles.date}>
              {formatDate(selectedPrompt.updated_at)}
            </span>
            {selectedPrompt.updated_by && (
              <>
                <span className={styles.separator}>•</span>
                <span className={styles.author}>{selectedPrompt.updated_by}</span>
              </>
            )}
          </div>
          {selectedPrompt.is_system && (
            <div className={styles.systemNote}>
              ⚠️ Системный промпт (нельзя удалить)
            </div>
          )}
          {selectedPrompt.use_minimal_base && (
            <div className={styles.minimalBaseNote}>
              ℹ️ Использует минимальный базовый промпт
            </div>
          )}
        </div>

        <div className={styles.footerRight}>
          <button
            className={styles.historyButton}
            onClick={() => setShowHistory(true)}
          >
            📜 История
          </button>
          <button
            className={`${styles.saveButton} ${hasChanges ? styles.hasChanges : ''}`}
            onClick={handleSave}
            disabled={!hasChanges || isSaving}
          >
            {isSaving ? 'Сохранение...' : '💾 Сохранить'}
          </button>
        </div>
      </div>

      {/* History modal */}
      {showHistory && (
        <PromptHistory
          promptId={selectedPrompt.id}
          promptName={selectedPrompt.name}
          onClose={() => setShowHistory(false)}
        />
      )}
    </div>
  )
}
