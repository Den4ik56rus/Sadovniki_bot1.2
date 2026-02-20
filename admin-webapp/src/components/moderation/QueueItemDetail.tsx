import { useState, useCallback } from 'react'
import { useModerationStore } from '@/store/moderationStore'
import styles from './QueueItemDetail.module.css'

export function QueueItemDetail() {
  const {
    selectedItem, aiEditResult, isEditingAI,
    setCategory, updateAnswer, editAnswerAI, clearAIEdit,
    approveItem, rejectItem, fetchQueue,
  } = useModerationStore()

  const [editMode, setEditMode] = useState<'none' | 'manual' | 'ai'>('none')
  const [editText, setEditText] = useState('')
  const [aiInstructions, setAiInstructions] = useState('')
  const [categoryInput, setCategoryInput] = useState('')
  const [showCategoryEditor, setShowCategoryEditor] = useState(false)
  const [saving, setSaving] = useState(false)

  const item = selectedItem
  if (!item) return null

  const handleSaveCategory = useCallback(async () => {
    if (!categoryInput.trim()) return
    setSaving(true)
    await setCategory(item.id, categoryInput.trim())
    setShowCategoryEditor(false)
    setSaving(false)
  }, [item.id, categoryInput, setCategory])

  const handleStartManualEdit = () => {
    setEditMode('manual')
    setEditText(item.answer || '')
    clearAIEdit()
  }

  const handleSaveManualEdit = async () => {
    if (!editText.trim()) return
    setSaving(true)
    const ok = await updateAnswer(item.id, editText.trim())
    if (ok) setEditMode('none')
    setSaving(false)
  }

  const handleStartAIEdit = () => {
    setEditMode('ai')
    setAiInstructions('')
    clearAIEdit()
  }

  const handleGenerateAI = async () => {
    if (!aiInstructions.trim()) return
    await editAnswerAI(item.id, aiInstructions.trim())
  }

  const handleAcceptAI = async () => {
    if (!aiEditResult) return
    setSaving(true)
    const ok = await updateAnswer(item.id, aiEditResult)
    if (ok) {
      setEditMode('none')
      clearAIEdit()
    }
    setSaving(false)
  }

  const handleApprove = async () => {
    setSaving(true)
    const ok = await approveItem(item.id)
    if (ok) fetchQueue()
    setSaving(false)
  }

  const handleReject = async () => {
    setSaving(true)
    const ok = await rejectItem(item.id)
    if (ok) fetchQueue()
    setSaving(false)
  }

  const isPending = item.status === 'pending'

  return (
    <div className={styles.detail}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h3 className={styles.title}>Кандидат #{item.id}</h3>
          <span className={`${styles.statusBadge} ${styles[`status_${item.status}`]}`}>
            {item.status === 'pending' ? 'Ожидает' : item.status === 'approved' ? 'Одобрен' : 'Отклонён'}
          </span>
        </div>
        {item.username && (
          <span className={styles.userInfo}>@{item.username}</span>
        )}
      </div>

      {/* Category */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <span className={styles.sectionLabel}>Категория</span>
          {isPending && !showCategoryEditor && (
            <button
              className={styles.editBtn}
              onClick={() => {
                setCategoryInput(item.category_guess || '')
                setShowCategoryEditor(true)
              }}
            >
              Изменить
            </button>
          )}
        </div>
        {showCategoryEditor ? (
          <div className={styles.categoryEditor}>
            <input
              className={styles.categoryInput}
              value={categoryInput}
              onChange={(e) => setCategoryInput(e.target.value)}
              placeholder="питание растений / малина"
              autoFocus
            />
            <div className={styles.categoryHint}>
              Формат: тип консультации / культура
            </div>
            <div className={styles.categoryActions}>
              <button
                className={styles.btnPrimary}
                onClick={handleSaveCategory}
                disabled={saving || !categoryInput.trim()}
              >
                Сохранить
              </button>
              <button
                className={styles.btnSecondary}
                onClick={() => setShowCategoryEditor(false)}
              >
                Отмена
              </button>
            </div>
          </div>
        ) : (
          <div className={styles.categoryValue}>
            {item.category_guess || <span className={styles.missing}>не определена</span>}
          </div>
        )}
      </div>

      {/* Question */}
      <div className={styles.section}>
        <div className={styles.sectionLabel}>Вопрос</div>
        <div className={styles.textBlock}>{item.question || '—'}</div>
      </div>

      {/* Answer */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <span className={styles.sectionLabel}>Ответ</span>
          {isPending && editMode === 'none' && (
            <div className={styles.editActions}>
              <button className={styles.editBtn} onClick={handleStartManualEdit}>
                Редактировать
              </button>
              <button className={styles.editBtn} onClick={handleStartAIEdit}>
                Редактировать с AI
              </button>
            </div>
          )}
        </div>

        {editMode === 'manual' ? (
          <div className={styles.editArea}>
            <textarea
              className={styles.textarea}
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              rows={10}
            />
            <div className={styles.editAreaActions}>
              <button className={styles.btnPrimary} onClick={handleSaveManualEdit} disabled={saving}>
                Сохранить
              </button>
              <button className={styles.btnSecondary} onClick={() => setEditMode('none')}>
                Отмена
              </button>
            </div>
          </div>
        ) : editMode === 'ai' ? (
          <div className={styles.aiEditArea}>
            {!aiEditResult ? (
              <>
                <div className={styles.textBlock}>{item.answer || '—'}</div>
                <div className={styles.aiInstructions}>
                  <label className={styles.aiLabel}>Инструкции для AI:</label>
                  <textarea
                    className={styles.textarea}
                    value={aiInstructions}
                    onChange={(e) => setAiInstructions(e.target.value)}
                    rows={3}
                    placeholder="Добавь информацию про дозировку..."
                  />
                  <div className={styles.editAreaActions}>
                    <button
                      className={styles.btnPrimary}
                      onClick={handleGenerateAI}
                      disabled={isEditingAI || !aiInstructions.trim()}
                    >
                      {isEditingAI ? 'Генерация...' : 'Сгенерировать'}
                    </button>
                    <button className={styles.btnSecondary} onClick={() => setEditMode('none')}>
                      Отмена
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <>
                <label className={styles.aiLabel}>Результат AI:</label>
                <div className={styles.aiResultBlock}>{aiEditResult}</div>
                <div className={styles.editAreaActions}>
                  <button className={styles.btnPrimary} onClick={handleAcceptAI} disabled={saving}>
                    Принять
                  </button>
                  <button className={styles.btnSecondary} onClick={() => clearAIEdit()}>
                    Переделать
                  </button>
                  <button className={styles.btnSecondary} onClick={() => setEditMode('none')}>
                    Отмена
                  </button>
                </div>
              </>
            )}
          </div>
        ) : (
          <div className={styles.textBlock}>{item.answer || '—'}</div>
        )}
      </div>

      {/* Action buttons */}
      {isPending && (
        <div className={styles.actionBar}>
          <button
            className={styles.btnApprove}
            onClick={handleApprove}
            disabled={saving}
          >
            В базу знаний
          </button>
          <button
            className={styles.btnReject}
            onClick={handleReject}
            disabled={saving}
          >
            Отклонить
          </button>
        </div>
      )}
    </div>
  )
}
