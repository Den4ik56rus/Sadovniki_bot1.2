// Buyer Column Component (based on KanbanColumn)
import { useState, useRef, useEffect } from 'react'
import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import type { Buyer, BuyerStatus } from '@/types'
import { useBuyersStore } from '@/store'
import { BuyerCard } from './BuyerCard'
import styles from '../crm/KanbanColumn.module.css'

interface BuyerColumnProps {
  id: BuyerStatus
  buyers: Buyer[]
  count: number
  totalValue: number
  onBuyerClick: (buyerId: number) => void
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

export function BuyerColumn({ id, buyers, count, totalValue, onBuyerClick }: BuyerColumnProps) {
  const {
    isSettingsMode,
    columnConfigs,
    updateColumnTitle,
    updateColumnColor,
    addColumnAfter,
    deleteColumn,
  } = useBuyersStore()

  const { setNodeRef, isOver } = useDroppable({
    id,
    data: {
      type: 'column',
      status: id,
    },
    disabled: isSettingsMode,
  })

  const columnConfig = columnConfigs.find((c) => c.id === id)!
  const columnTitle = columnConfig.title
  const columnColor = columnConfig.color
  const isSystemColumn = columnConfig.is_system

  const [showColorPicker, setShowColorPicker] = useState(false)
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [tempTitle, setTempTitle] = useState(columnTitle)
  const colorPickerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const buyerIds = buyers.map((b) => b.id)

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

  useEffect(() => {
    if (isEditingTitle && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isEditingTitle])

  useEffect(() => {
    setTempTitle(columnTitle)
  }, [columnTitle])

  const handleTitleClick = () => {
    if (isSettingsMode) {
      setTempTitle(columnTitle)
      setIsEditingTitle(true)
    }
  }

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTempTitle(e.target.value)
  }

  const handleTitleBlur = () => {
    updateColumnTitle(id, tempTitle)
    setIsEditingTitle(false)
  }

  const handleTitleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      updateColumnTitle(id, tempTitle)
      setIsEditingTitle(false)
    }
    if (e.key === 'Escape') {
      setTempTitle(columnTitle)
      setIsEditingTitle(false)
    }
  }

  const handleColorSelect = (color: string) => {
    updateColumnColor(id, color)
    setShowColorPicker(false)
  }

  const handleAddColumn = () => {
    addColumnAfter(id)
  }

  const handleDeleteColumn = () => {
    if (isSystemColumn) {
      alert(`Нельзя удалить системный этап "${columnTitle}".`)
      return
    }
    if (count > 0) {
      alert(`Нельзя удалить этап "${columnTitle}" — в нём есть ${count} покупателей. Сначала переместите их в другой этап.`)
      return
    }
    if (confirm(`Удалить этап "${columnTitle}"?`)) {
      deleteColumn(id)
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
                {!isSystemColumn && (
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
                  style={{ backgroundColor: columnColor }}
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
                {columnTitle}
              </h3>
              {isSettingsMode && (
                <div className={styles.editActions}>
                  {!isSystemColumn && (
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
                    style={{ backgroundColor: columnColor }}
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

        {isSettingsMode && showColorPicker && (
          <div className={styles.colorPickerDropdown} ref={colorPickerRef}>
            {COLOR_OPTIONS.map((color) => (
              <button
                key={color.value}
                className={`${styles.colorOption} ${columnColor === color.value ? styles.colorOptionActive : ''}`}
                style={{ backgroundColor: color.value }}
                onClick={() => handleColorSelect(color.value)}
                title={color.name}
              />
            ))}
          </div>
        )}

        <div className={`${styles.headerStats} ${isSettingsMode ? styles.headerStatsHidden : ''}`}>
          <span className={styles.count}>{count} покупателей</span>
          {totalValue > 0 && (
            <>
              <span className={styles.statDivider}>:</span>
              <span className={styles.value}>{totalValue.toFixed(0)} ₽</span>
            </>
          )}
        </div>

        <div className={styles.colorBarWrapper}>
          <div
            className={styles.colorBar}
            style={{ backgroundColor: columnColor }}
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

      {isSettingsMode ? (
        <div className={styles.triggersSection}>
          <button className={styles.addTriggerBtn}>
            Добавить триггер
          </button>
          <div className={styles.triggersList}>
          </div>
        </div>
      ) : (
        <>
          <button className={styles.quickAdd}>
            Быстрое добавление
          </button>
          <div className={styles.content}>
            <SortableContext items={buyerIds} strategy={verticalListSortingStrategy}>
              {buyers.map((buyer) => (
                <BuyerCard
                  key={buyer.id}
                  buyer={buyer}
                  onClick={() => onBuyerClick(buyer.id)}
                />
              ))}
            </SortableContext>
          </div>
        </>
      )}
    </div>
  )
}
