// Tags Section Component
import { useState } from 'react'
import type { ClientTag } from '@/types'
import { api } from '@/services/api'
import styles from './TagsSection.module.css'

interface TagsSectionProps {
  clientTags: ClientTag[]
  allTags: ClientTag[]
  onChange: (tagIds: number[]) => void
}

export function TagsSection({ clientTags, allTags, onChange }: TagsSectionProps) {
  const [isAdding, setIsAdding] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [newTagName, setNewTagName] = useState('')
  const [newTagColor, setNewTagColor] = useState('#6B7280')

  const clientTagIds = clientTags.map(t => t.id)
  const availableTags = allTags.filter(t => !clientTagIds.includes(t.id))

  const handleAddTag = (tagId: number) => {
    onChange([...clientTagIds, tagId])
    setIsAdding(false)
  }

  const handleRemoveTag = (tagId: number) => {
    onChange(clientTagIds.filter(id => id !== tagId))
  }

  const handleCreateTag = async () => {
    if (!newTagName.trim()) return

    try {
      const newTag = await api.createTag({
        name: newTagName.trim(),
        color: newTagColor,
      })
      onChange([...clientTagIds, newTag.id])
      setNewTagName('')
      setNewTagColor('#6B7280')
      setIsCreating(false)
      setIsAdding(false)
    } catch (e) {
      console.error('Failed to create tag:', e)
    }
  }

  const PRESET_COLORS = [
    '#EF4444', // red
    '#F59E0B', // amber
    '#10B981', // green
    '#3B82F6', // blue
    '#8B5CF6', // purple
    '#EC4899', // pink
    '#6B7280', // gray
    '#FFD700', // gold
  ]

  return (
    <div className={styles.section}>
      <h4 className={styles.sectionTitle}>Теги</h4>

      <div className={styles.tagsList}>
        {clientTags.map(tag => (
          <span
            key={tag.id}
            className={styles.tag}
            style={{ backgroundColor: tag.color }}
          >
            {tag.name}
            <button
              className={styles.removeTag}
              onClick={() => handleRemoveTag(tag.id)}
              title="Удалить тег"
            >
              ×
            </button>
          </span>
        ))}

        {!isAdding && (
          <button
            className={styles.addTagBtn}
            onClick={() => setIsAdding(true)}
          >
            + Добавить
          </button>
        )}
      </div>

      {isAdding && (
        <div className={styles.addTagDropdown}>
          {!isCreating ? (
            <>
              {availableTags.length > 0 ? (
                <div className={styles.tagOptions}>
                  {availableTags.map(tag => (
                    <button
                      key={tag.id}
                      className={styles.tagOption}
                      style={{ backgroundColor: tag.color }}
                      onClick={() => handleAddTag(tag.id)}
                    >
                      {tag.name}
                    </button>
                  ))}
                </div>
              ) : (
                <p className={styles.noTags}>Нет доступных тегов</p>
              )}

              <button
                className={styles.createTagBtn}
                onClick={() => setIsCreating(true)}
              >
                + Создать новый тег
              </button>

              <button
                className={styles.cancelBtn}
                onClick={() => setIsAdding(false)}
              >
                Отмена
              </button>
            </>
          ) : (
            <div className={styles.createForm}>
              <input
                type="text"
                className={styles.input}
                placeholder="Название тега"
                value={newTagName}
                onChange={(e) => setNewTagName(e.target.value)}
                autoFocus
              />

              <div className={styles.colorPicker}>
                {PRESET_COLORS.map(color => (
                  <button
                    key={color}
                    className={`${styles.colorOption} ${newTagColor === color ? styles.colorSelected : ''}`}
                    style={{ backgroundColor: color }}
                    onClick={() => setNewTagColor(color)}
                  />
                ))}
              </div>

              <div className={styles.createActions}>
                <button
                  className={styles.createBtn}
                  onClick={handleCreateTag}
                  disabled={!newTagName.trim()}
                >
                  Создать
                </button>
                <button
                  className={styles.cancelBtn}
                  onClick={() => {
                    setIsCreating(false)
                    setNewTagName('')
                  }}
                >
                  Отмена
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
