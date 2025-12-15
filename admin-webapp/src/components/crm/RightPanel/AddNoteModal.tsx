// Add Note Modal
import { useState } from 'react'
import styles from './AddNoteModal.module.css'

interface AddNoteModalProps {
  onSubmit: (text: string) => void
  onClose: () => void
}

export function AddNoteModal({ onSubmit, onClose }: AddNoteModalProps) {
  const [text, setText] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    onSubmit(text.trim())
  }

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  return (
    <div className={styles.backdrop} onClick={handleBackdropClick}>
      <div className={styles.modal}>
        <div className={styles.header}>
          <h3 className={styles.title}>Новая заметка</h3>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <textarea
              className={styles.textarea}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Введите текст заметки..."
              rows={5}
              autoFocus
              required
            />
          </div>

          <div className={styles.actions}>
            <button type="button" className={styles.cancelBtn} onClick={onClose}>
              Отмена
            </button>
            <button
              type="submit"
              className={styles.submitBtn}
              disabled={!text.trim()}
            >
              Добавить
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
