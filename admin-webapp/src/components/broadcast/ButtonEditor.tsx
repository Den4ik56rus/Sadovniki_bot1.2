// Button Editor — редактор inline-кнопок для рассылки

import { useState } from 'react'
import type { BroadcastButton } from '@/types'
import styles from './ButtonEditor.module.css'

interface Props {
  buttons: BroadcastButton[]
  onChange: (buttons: BroadcastButton[]) => void
}

const MAX_ROWS = 5
const MAX_BUTTONS_PER_ROW = 2

export function ButtonEditor({ buttons, onChange }: Props) {
  const [enabled, setEnabled] = useState(buttons.length > 0)

  const handleToggle = () => {
    const next = !enabled
    setEnabled(next)
    if (!next) {
      onChange([])
    }
  }

  // Группируем кнопки по рядам
  const rows: Record<number, BroadcastButton[]> = {}
  for (const btn of buttons) {
    const r = btn.row ?? 0
    if (!rows[r]) rows[r] = []
    rows[r].push(btn)
  }
  const rowKeys = Object.keys(rows).map(Number).sort((a, b) => a - b)
  const rowCount = rowKeys.length || 0

  const updateButton = (rowIdx: number, btnIdx: number, updates: Partial<BroadcastButton>) => {
    const updated = buttons.map((b) => {
      // Находим кнопку в нужном ряду
      const rowButtons = buttons.filter((x) => x.row === rowIdx)
      if (b === rowButtons[btnIdx]) {
        return { ...b, ...updates }
      }
      return b
    })
    onChange(updated)
  }

  const addRow = () => {
    const newRow = rowCount > 0 ? Math.max(...rowKeys) + 1 : 0
    const optIdx = buttons.filter((b) => b.type === 'quick_reply').length
    onChange([...buttons, {
      row: newRow,
      text: '',
      type: 'quick_reply',
      option_key: `opt_${optIdx}`,
    }])
  }

  const addButtonToRow = (rowIdx: number) => {
    const rowButtons = buttons.filter((b) => b.row === rowIdx)
    if (rowButtons.length >= MAX_BUTTONS_PER_ROW) return
    const optIdx = buttons.filter((b) => b.type === 'quick_reply').length
    onChange([...buttons, {
      row: rowIdx,
      text: '',
      type: 'quick_reply',
      option_key: `opt_${optIdx}`,
    }])
  }

  const removeButton = (rowIdx: number, btnIdx: number) => {
    const rowButtons = buttons.filter((b) => b.row === rowIdx)
    const target = rowButtons[btnIdx]
    const updated = buttons.filter((b) => b !== target)
    // Если ряд стал пустым — ничего не делаем, ряд просто исчезнет
    onChange(updated)
  }

  const removeRow = (rowIdx: number) => {
    onChange(buttons.filter((b) => b.row !== rowIdx))
  }

  return (
    <div className={styles.container}>
      <label className={styles.toggleLabel}>
        <input
          type="checkbox"
          checked={enabled}
          onChange={handleToggle}
        />
        <span>Добавить кнопки</span>
      </label>

      {enabled && (
        <div className={styles.editorForm}>
          {rowKeys.map((rowIdx) => {
            const rowButtons = buttons.filter((b) => b.row === rowIdx)
            return (
              <div key={rowIdx} className={styles.rowBlock}>
                <div className={styles.rowHeader}>
                  <span className={styles.rowLabel}>Ряд {rowIdx + 1}</span>
                  <button
                    className={styles.removeRowBtn}
                    onClick={() => removeRow(rowIdx)}
                    type="button"
                    title="Удалить ряд"
                  >
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M3 3L9 9M9 3L3 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  </button>
                </div>
                <div className={styles.rowButtons}>
                  {rowButtons.map((btn, btnIdx) => (
                    <div key={btnIdx} className={styles.buttonCard}>
                      <div className={styles.buttonFields}>
                        <input
                          className={styles.buttonTextInput}
                          type="text"
                          placeholder="Текст кнопки"
                          value={btn.text}
                          maxLength={64}
                          onChange={(e) => updateButton(rowIdx, btnIdx, { text: e.target.value })}
                        />
                        <select
                          className={styles.typeSelect}
                          value={btn.type}
                          onChange={(e) => {
                            const newType = e.target.value as 'url' | 'quick_reply'
                            const optIdx = buttons.filter((b) => b.type === 'quick_reply').length
                            updateButton(rowIdx, btnIdx, {
                              type: newType,
                              url: newType === 'url' ? (btn.url || '') : undefined,
                              option_key: newType === 'quick_reply' ? (btn.option_key || `opt_${optIdx}`) : undefined,
                            })
                          }}
                        >
                          <option value="quick_reply">Ответ</option>
                          <option value="url">Ссылка</option>
                        </select>
                        {btn.type === 'url' && (
                          <input
                            className={styles.urlInput}
                            type="url"
                            placeholder="https://..."
                            value={btn.url || ''}
                            onChange={(e) => updateButton(rowIdx, btnIdx, { url: e.target.value })}
                          />
                        )}
                        {btn.type === 'url' && (
                          <div className={styles.urlHint}>
                            Telegram не отслеживает клики по ссылкам
                          </div>
                        )}
                      </div>
                      <button
                        className={styles.removeBtnBtn}
                        onClick={() => removeButton(rowIdx, btnIdx)}
                        type="button"
                        title="Удалить кнопку"
                      >
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                          <path d="M3 3L9 9M9 3L3 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                        </svg>
                      </button>
                    </div>
                  ))}
                  {rowButtons.length < MAX_BUTTONS_PER_ROW && (
                    <button
                      className={styles.addBtnInRow}
                      onClick={() => addButtonToRow(rowIdx)}
                      type="button"
                    >
                      + кнопку
                    </button>
                  )}
                </div>
              </div>
            )
          })}

          {rowCount < MAX_ROWS && (
            <button
              className={styles.addRowBtn}
              onClick={addRow}
              type="button"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M6 1V11M1 6H11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              Добавить ряд кнопок
            </button>
          )}
        </div>
      )}
    </div>
  )
}
