// Slide Viewer — view and edit individual slide with version history
import { useState } from 'react'
import { api } from '@/services/api'
import type { PresentationSlide } from '@/types'
import styles from './PresentationsPage.module.css'

interface Props {
  slide: PresentationSlide
  onEdit: () => void
}

export function SlideViewer({ slide, onEdit }: Props) {
  const [editInstruction, setEditInstruction] = useState('')
  const [isEditing, setIsEditing] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [selectedVersionIdx, setSelectedVersionIdx] = useState<number>(
    slide.versions.length - 1
  )

  const currentVersion = slide.versions[selectedVersionIdx] ?? null

  const handleEdit = async () => {
    if (!editInstruction.trim() || isEditing) return
    setIsEditing(true)
    setEditError(null)

    try {
      await api.editSlide(slide.id, editInstruction.trim())
      setEditInstruction('')
      onEdit() // Refresh parent
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Ошибка при редактировании')
    } finally {
      setIsEditing(false)
    }
  }

  return (
    <div className={styles.slideViewerContainer}>
      <h3 className={styles.sectionTitle}>
        Слайд {slide.slide_index + 1}: {slide.slide_title || 'Без названия'}
      </h3>

      {/* Current image */}
      <div className={styles.slideImageContainer}>
        {currentVersion?.image_path ? (
          <img
            className={styles.slideImageFull}
            src={api.getSlideImageUrl(currentVersion.id)}
            alt={slide.slide_title || `Слайд ${slide.slide_index + 1}`}
          />
        ) : (
          <div className={styles.slideImagePlaceholder}>
            {currentVersion?.status === 'generating' ? 'Генерация...' : 'Изображение недоступно'}
          </div>
        )}
      </div>

      {/* Version thumbnails */}
      {slide.versions.length > 1 && (
        <div className={styles.versionsRow}>
          <span className={styles.versionsLabel}>Версии:</span>
          {slide.versions.map((ver, idx) => (
            <button
              key={ver.id}
              className={`${styles.versionThumb} ${idx === selectedVersionIdx ? styles.versionThumbActive : ''}`}
              onClick={() => setSelectedVersionIdx(idx)}
              title={ver.edit_instruction || `Версия ${ver.version_number}`}
            >
              {ver.image_path ? (
                <img src={api.getSlideImageUrl(ver.id)} alt={`v${ver.version_number}`} />
              ) : (
                <span>v{ver.version_number}</span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Version info */}
      {currentVersion && (
        <div className={styles.versionInfo}>
          <span>Версия {currentVersion.version_number}</span>
          {currentVersion.edit_instruction && (
            <span className={styles.versionInstruction}>
              Правка: {currentVersion.edit_instruction}
            </span>
          )}
          <span>${currentVersion.nbp_cost_usd.toFixed(4)}</span>
          <span className={`${styles.statusBadge} ${
            currentVersion.status === 'completed' ? styles.statusCompleted :
            currentVersion.status === 'failed' ? styles.statusFailed :
            currentVersion.status === 'generating' ? styles.statusGenerating :
            styles.statusDraft
          }`}>
            {currentVersion.status}
          </span>
        </div>
      )}

      {/* Edit form */}
      <div className={styles.editSection}>
        <label className={styles.label}>Инструкция по редактированию</label>
        <div className={styles.editRow}>
          <input
            className={styles.textInput}
            type="text"
            value={editInstruction}
            placeholder="Сделай фон светлее, увеличь заголовок..."
            onChange={e => setEditInstruction(e.target.value)}
            disabled={isEditing}
            onKeyDown={e => { if (e.key === 'Enter') handleEdit() }}
          />
          <button
            className={styles.generateButton}
            onClick={handleEdit}
            disabled={isEditing || !editInstruction.trim()}
          >
            {isEditing ? <span className={styles.spinner} /> : 'Редактировать'}
          </button>
        </div>
        {editError && <div className={styles.error}>{editError}</div>}
      </div>

      {/* Slide prompt (collapsible) */}
      <details className={styles.promptDetails}>
        <summary className={styles.promptSummary}>NBP промпт</summary>
        <pre className={styles.promptText}>{slide.slide_prompt}</pre>
      </details>

      {slide.slide_notes && (
        <details className={styles.promptDetails}>
          <summary className={styles.promptSummary}>Заметки</summary>
          <p className={styles.notesText}>{slide.slide_notes}</p>
        </details>
      )}
    </div>
  )
}
