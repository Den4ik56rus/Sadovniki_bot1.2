/**
 * Модальное окно с историей версий промпта.
 *
 * Отображает:
 * - Список версий с датами и авторами
 * - Возможность просмотреть diff между версией и актуальным контентом
 * - Кнопка "Восстановить" для отката к версии
 */

import { useEffect, useState } from 'react'
import { usePromptStore } from '@/store/promptStore'
import { api } from '@/services/api'
import type { PromptHistoryItem, DiffResult } from '@/types'
import styles from './PromptHistory.module.css'

interface PromptHistoryProps {
  promptId: number
  promptName: string
  onClose: () => void
}

export function PromptHistory({ promptId, promptName, onClose }: PromptHistoryProps) {
  const { history, isLoadingHistory, isSaving, fetchHistory, revertToVersion } = usePromptStore()
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null)
  const [diffResult, setDiffResult] = useState<DiffResult | null>(null)
  const [isLoadingDiff, setIsLoadingDiff] = useState(false)
  const [confirmRevert, setConfirmRevert] = useState<number | null>(null)
  const [showMode, setShowMode] = useState<'diff' | 'content'>('diff')

  useEffect(() => {
    fetchHistory(promptId)
  }, [promptId, fetchHistory])

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

  const handleSelectVersion = async (item: PromptHistoryItem) => {
    if (selectedVersion === item.version) {
      setSelectedVersion(null)
      setDiffResult(null)
      return
    }

    setSelectedVersion(item.version)
    setIsLoadingDiff(true)

    try {
      const response = await api.getPromptVersionDiff(promptId, item.version)
      setDiffResult(response.diff)
    } catch (error) {
      console.error('Error loading diff:', error)
      setDiffResult(null)
    } finally {
      setIsLoadingDiff(false)
    }
  }

  const handleRevert = async (version: number) => {
    await revertToVersion(promptId, version)
    setConfirmRevert(null)
    onClose()
  }

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  const getSelectedItem = () => {
    return history.find(h => h.version === selectedVersion)
  }

  return (
    <div className={styles.backdrop} onClick={handleBackdropClick}>
      <div className={styles.modal}>
        <div className={styles.header}>
          <h3 className={styles.title}>История изменений</h3>
          <span className={styles.promptName}>{promptName}</span>
          <button className={styles.closeButton} onClick={onClose}>
            ×
          </button>
        </div>

        <div className={styles.content}>
          {isLoadingHistory ? (
            <div className={styles.loading}>Загрузка истории...</div>
          ) : history.length === 0 ? (
            <div className={styles.empty}>
              <div className={styles.emptyIcon}>📋</div>
              <div className={styles.emptyText}>История изменений пуста</div>
              <div className={styles.emptySubtext}>
                Изменения будут отображаться здесь после редактирования промпта
              </div>
            </div>
          ) : (
            <div className={styles.historyLayout}>
              {/* Список версий слева */}
              <div className={styles.historyList}>
                {history.map((item) => (
                  <div
                    key={item.id}
                    className={`${styles.historyItem} ${selectedVersion === item.version ? styles.selected : ''}`}
                    onClick={() => handleSelectVersion(item)}
                  >
                    <div className={styles.historyHeader}>
                      <span className={styles.version}>v{item.version}</span>
                      <span className={styles.date}>{formatDate(item.created_at)}</span>
                    </div>
                    {item.changed_by && (
                      <span className={styles.author}>{item.changed_by}</span>
                    )}
                    <button
                      className={styles.revertButton}
                      onClick={(e) => {
                        e.stopPropagation()
                        setConfirmRevert(item.version)
                      }}
                      disabled={isSaving}
                    >
                      ↩️
                    </button>
                  </div>
                ))}
              </div>

              {/* Diff справа */}
              <div className={styles.diffPanel}>
                {selectedVersion === null ? (
                  <div className={styles.diffPlaceholder}>
                    Выберите версию слева для просмотра изменений
                  </div>
                ) : isLoadingDiff ? (
                  <div className={styles.diffLoading}>Загрузка diff...</div>
                ) : diffResult ? (
                  <>
                    <div className={styles.diffHeader}>
                      <div className={styles.diffStats}>
                        <span className={styles.diffAdded}>+{diffResult.lines_added}</span>
                        <span className={styles.diffRemoved}>-{diffResult.lines_removed}</span>
                      </div>
                      <div className={styles.diffTabs}>
                        <button
                          className={`${styles.diffTab} ${showMode === 'diff' ? styles.activeTab : ''}`}
                          onClick={() => setShowMode('diff')}
                        >
                          Diff
                        </button>
                        <button
                          className={`${styles.diffTab} ${showMode === 'content' ? styles.activeTab : ''}`}
                          onClick={() => setShowMode('content')}
                        >
                          Полный текст
                        </button>
                      </div>
                    </div>

                    {showMode === 'diff' ? (
                      <div className={styles.diffContent}>
                        {diffResult.changes.length === 0 ? (
                          <div className={styles.noDiff}>Нет изменений</div>
                        ) : (
                          diffResult.changes.map((change, idx) => (
                            <div
                              key={idx}
                              className={`${styles.diffLine} ${styles[change.type]}`}
                            >
                              <span className={styles.lineNumber}>
                                {change.old_line_number || change.new_line_number || ''}
                              </span>
                              <span className={styles.linePrefix}>
                                {change.type === 'added' ? '+' : change.type === 'removed' ? '-' : ' '}
                              </span>
                              <span className={styles.lineContent}>{change.line}</span>
                            </div>
                          ))
                        )}
                      </div>
                    ) : (
                      <div className={styles.contentPreview}>
                        <pre>{getSelectedItem()?.content}</pre>
                      </div>
                    )}
                  </>
                ) : (
                  <div className={styles.diffError}>Ошибка загрузки diff</div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Confirmation dialog */}
        {confirmRevert !== null && (
          <div className={styles.confirmBackdrop}>
            <div className={styles.confirmDialog}>
              <h4 className={styles.confirmTitle}>Восстановить версию {confirmRevert}?</h4>
              <p className={styles.confirmText}>
                Текущее содержимое промпта будет заменено на версию {confirmRevert}.
                История сохранится.
              </p>
              <div className={styles.confirmButtons}>
                <button
                  className={styles.cancelButton}
                  onClick={() => setConfirmRevert(null)}
                >
                  Отмена
                </button>
                <button
                  className={styles.confirmButton}
                  onClick={() => handleRevert(confirmRevert)}
                  disabled={isSaving}
                >
                  {isSaving ? 'Восстановление...' : 'Восстановить'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
