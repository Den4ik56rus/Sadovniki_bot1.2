// Universal Funnel Column Component
import { useState, useRef, useEffect } from 'react'
import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import type { FunnelClient } from '@/types'
import { useFunnelStore } from '@/store/funnelStore'
import { FunnelClientCard } from './FunnelClientCard'
import { StageTriggerEditor } from './StageTriggerEditor'
import styles from './FunnelColumn.module.css'

interface FunnelColumnProps {
  stageKey: string
  title: string
  color: string
  clients: FunnelClient[]
  count: number
  totalValue: number
  onClientClick: (clientId: number) => void
}

const COLOR_OPTIONS = [
  { name: 'Синий', value: '#3B82F6' },
  { name: 'Фиолетовый', value: '#8B5CF6' },
  { name: 'Жёлтый', value: '#F59E0B' },
  { name: 'Зелёный', value: '#22C55E' },
  { name: 'Красный', value: '#EF4444' },
  { name: 'Розовый', value: '#EC4899' },
  { name: 'Бирюзовый', value: '#14B8A6' },
  { name: 'Серый', value: '#6B7280' },
]

export function FunnelColumn({
  stageKey,
  title,
  color,
  clients,
  count,
  totalValue,
  onClientClick,
}: FunnelColumnProps) {
  const {
    isSettingsMode,
    currentFunnelId,
    stages,
    triggers,
    updateStage,
    createStage,
    deleteStage,
  } = useFunnelStore()

  const stage = stages.find((s) => s.stage_key === stageKey)
  const isSystemStage = stage?.is_system ?? false

  // Disable droppable in settings mode
  const { setNodeRef, isOver } = useDroppable({
    id: stageKey,
    data: {
      type: 'column',
      stageKey,
    },
    disabled: isSettingsMode,
  })

  const [showColorPicker, setShowColorPicker] = useState(false)
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [tempTitle, setTempTitle] = useState(title)
  const colorPickerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const clientIds = clients.map((c) => c.id)

  // Close color picker when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (colorPickerRef.current && !colorPickerRef.current.contains(event.target as Node)) {
        setShowColorPicker(false)
      }
    }
    if (showColorPicker) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showColorPicker])

  // Focus input when editing
  useEffect(() => {
    if (isEditingTitle && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isEditingTitle])

  // Reset temp title when title changes
  useEffect(() => {
    setTempTitle(title)
  }, [title])

  const handleTitleClick = () => {
    if (isSettingsMode) {
      setTempTitle(title)
      setIsEditingTitle(true)
    }
  }

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTempTitle(e.target.value)
  }

  const handleTitleBlur = () => {
    if (currentFunnelId && tempTitle.trim()) {
      updateStage(currentFunnelId, stageKey, { title: tempTitle.trim() })
    }
    setIsEditingTitle(false)
  }

  const handleTitleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      if (currentFunnelId && tempTitle.trim()) {
        updateStage(currentFunnelId, stageKey, { title: tempTitle.trim() })
      }
      setIsEditingTitle(false)
    }
    if (e.key === 'Escape') {
      setTempTitle(title)
      setIsEditingTitle(false)
    }
  }

  const handleColorSelect = (newColor: string) => {
    if (currentFunnelId) {
      updateStage(currentFunnelId, stageKey, { color: newColor })
    }
    setShowColorPicker(false)
  }

  const handleAddColumn = async () => {
    if (!currentFunnelId) return
    await createStage(currentFunnelId, {
      title: 'Новый этап',
      color: '#6B7280',
    })
  }

  const handleDeleteColumn = async () => {
    if (!currentFunnelId) return

    if (isSystemStage) {
      alert(`Нельзя удалить системный этап "${title}".`)
      return
    }
    if (count > 0) {
      alert(`Нельзя удалить этап "${title}" — в нём есть ${count} клиентов. Сначала переместите их в другой этап.`)
      return
    }
    if (confirm(`Удалить этап "${title}"?`)) {
      await deleteStage(currentFunnelId, stageKey)
      setIsEditingTitle(false)
    }
  }

  return (
    <div
      ref={setNodeRef}
      className={`${styles.column} ${isOver && !isSettingsMode ? styles.columnOver : ''}`}
    >
      {/* Column Header */}
      <div className={styles.header}>
        <div className={styles.headerTop}>
          {/* Title - editable in settings mode */}
          {isSettingsMode && isEditingTitle ? (
            <div className={styles.editRow}>
              <input
                ref={inputRef}
                type="text"
                className={styles.titleInput}
                value={tempTitle}
                onChange={handleTitleChange}
                onKeyDown={handleTitleKeyDown}
                onBlur={handleTitleBlur}
              />
              <div className={styles.editActions}>
                {!isSystemStage && (
                  <button
                    className={styles.deleteBtn}
                    title="Удалить"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={handleDeleteColumn}
                  >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <path d="M2 4H14M5.33333 4V2.66667C5.33333 2.29848 5.63181 2 6 2H10C10.3682 2 10.6667 2.29848 10.6667 2.66667V4M6.66667 7.33333V11.3333M9.33333 7.33333V11.3333M3.33333 4L4 13.3333C4 13.7015 4.29848 14 4.66667 14H11.3333C11.7015 14 12 13.7015 12 13.3333L12.6667 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </button>
                )}
                <button
                  className={styles.colorBtn}
                  style={{ backgroundColor: color }}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={(e) => {
                    e.stopPropagation()
                    setShowColorPicker(!showColorPicker)
                  }}
                  title="Изменить цвет"
                />
              </div>
            </div>
          ) : (
            <div className={styles.titleBlock}>
              <h3
                className={`${styles.title} ${isSettingsMode ? styles.titleEditable : ''}`}
                onClick={handleTitleClick}
              >
                {title}
              </h3>
              {isSettingsMode && (
                <div className={styles.editActions}>
                  {!isSystemStage && (
                    <button
                      className={styles.deleteBtn}
                      title="Удалить"
                      onClick={handleDeleteColumn}
                    >
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path d="M2 4H14M5.33333 4V2.66667C5.33333 2.29848 5.63181 2 6 2H10C10.3682 2 10.6667 2.29848 10.6667 2.66667V4M6.66667 7.33333V11.3333M9.33333 7.33333V11.3333M3.33333 4L4 13.3333C4 13.7015 4.29848 14 4.66667 14H11.3333C11.7015 14 12 13.7015 12 13.3333L12.6667 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </button>
                  )}
                  <button
                    className={styles.colorBtn}
                    style={{ backgroundColor: color }}
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowColorPicker(!showColorPicker)
                    }}
                    title="Изменить цвет"
                  />
                </div>
              )}
            </div>
          )}

          {/* Settings button - only in normal mode */}
          {!isSettingsMode && (
            <div className={styles.headerActions}>
              <button
                className={styles.settingsBtn}
                title="Настройки"
              >
                ⋮
              </button>
            </div>
          )}
        </div>

        {/* Color picker dropdown */}
        {isSettingsMode && showColorPicker && (
          <div className={styles.colorPickerDropdown} ref={colorPickerRef}>
            {COLOR_OPTIONS.map((colorOpt) => (
              <button
                key={colorOpt.value}
                className={`${styles.colorOption} ${color === colorOpt.value ? styles.colorOptionActive : ''}`}
                style={{ backgroundColor: colorOpt.value }}
                onClick={() => handleColorSelect(colorOpt.value)}
                title={colorOpt.name}
              />
            ))}
          </div>
        )}

        {/* Stats - hidden in settings mode */}
        <div className={`${styles.headerStats} ${isSettingsMode ? styles.headerStatsHidden : ''}`}>
          <span className={styles.count}>{count} клиентов</span>
          {totalValue > 0 && (
            <>
              <span className={styles.statDivider}>:</span>
              <span className={styles.value}>{totalValue.toFixed(0)} ₽</span>
            </>
          )}
        </div>

        {/* Color bar */}
        <div className={styles.colorBarWrapper}>
          <div
            className={styles.colorBar}
            style={{ backgroundColor: color }}
          />
          {isSettingsMode && !isEditingTitle && (
            <div className={styles.colorBarActions}>
              <button
                className={styles.colorBarBtn}
                title="Добавить этап"
                onClick={handleAddColumn}
              >
                +
              </button>
              <div className={styles.colorBarDragHandle} title="Перетащите для перемещения">
                ⋮⋮
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Content depends on mode */}
      {isSettingsMode ? (
        <div className={styles.triggersSection}>
          {currentFunnelId && (
            <StageTriggerEditor
              funnelId={currentFunnelId}
              stageKey={stageKey}
              triggers={triggers}
            />
          )}
        </div>
      ) : (
        <>
          <button className={styles.quickAdd}>
            Быстрое добавление
          </button>
          <div className={styles.content}>
            <SortableContext items={clientIds} strategy={verticalListSortingStrategy}>
              {clients.map((client) => (
                <FunnelClientCard
                  key={client.id}
                  client={client}
                  onClick={() => onClientClick(client.id)}
                />
              ))}
            </SortableContext>
          </div>
        </>
      )}
    </div>
  )
}
