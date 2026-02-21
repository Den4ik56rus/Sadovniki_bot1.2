// Poll Editor — редактор опроса для рассылки

import { useState } from 'react'
import styles from './PollEditor.module.css'

interface PollState {
  question?: string
  options?: string[]
  isAnonymous?: boolean
  allowsMultiple?: boolean
}

interface Props {
  pollQuestion: string
  pollOptions: string[]
  pollIsAnonymous: boolean
  pollAllowsMultiple: boolean
  onChange: (update: PollState) => void
}

const MAX_QUESTION_LENGTH = 300
const MAX_OPTIONS = 10
const MIN_OPTIONS = 2

export function PollEditor({
  pollQuestion,
  pollOptions,
  pollIsAnonymous,
  pollAllowsMultiple,
  onChange,
}: Props) {
  const [enabled, setEnabled] = useState(!!pollQuestion)

  const handleToggle = () => {
    const next = !enabled
    setEnabled(next)
    if (!next) {
      onChange({ question: '', options: ['', ''] })
    }
  }

  const handleOptionChange = (index: number, value: string) => {
    const updated = [...pollOptions]
    updated[index] = value
    onChange({ options: updated })
  }

  const addOption = () => {
    if (pollOptions.length >= MAX_OPTIONS) return
    onChange({ options: [...pollOptions, ''] })
  }

  const removeOption = (index: number) => {
    if (pollOptions.length <= MIN_OPTIONS) return
    const updated = pollOptions.filter((_, i) => i !== index)
    onChange({ options: updated })
  }

  return (
    <div className={styles.container}>
      <label className={styles.toggleLabel}>
        <input
          type="checkbox"
          checked={enabled}
          onChange={handleToggle}
        />
        <span>Добавить опрос</span>
      </label>

      {enabled && (
        <div className={styles.pollForm}>
          {/* Question */}
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>
              Вопрос ({pollQuestion.length}/{MAX_QUESTION_LENGTH})
            </label>
            <input
              className={styles.questionInput}
              type="text"
              placeholder="Введите вопрос опроса..."
              value={pollQuestion}
              maxLength={MAX_QUESTION_LENGTH}
              onChange={(e) => onChange({ question: e.target.value })}
            />
          </div>

          {/* Options */}
          <div className={styles.fieldGroup}>
            <label className={styles.fieldLabel}>
              Варианты ответа ({pollOptions.length}/{MAX_OPTIONS})
            </label>
            <div className={styles.optionsList}>
              {pollOptions.map((opt, i) => (
                <div key={i} className={styles.optionRow}>
                  <span className={styles.optionNumber}>{i + 1}.</span>
                  <input
                    className={styles.optionInput}
                    type="text"
                    placeholder={`Вариант ${i + 1}`}
                    value={opt}
                    onChange={(e) => handleOptionChange(i, e.target.value)}
                    maxLength={100}
                  />
                  {pollOptions.length > MIN_OPTIONS && (
                    <button
                      className={styles.removeOptionBtn}
                      onClick={() => removeOption(i)}
                      title="Удалить вариант"
                      type="button"
                    >
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <path d="M3 3L9 9M9 3L3 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    </button>
                  )}
                </div>
              ))}
            </div>
            {pollOptions.length < MAX_OPTIONS && (
              <button
                className={styles.addOptionBtn}
                onClick={addOption}
                type="button"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M6 1V11M1 6H11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
                Добавить вариант
              </button>
            )}
          </div>

          {/* Checkboxes */}
          <div className={styles.checkboxes}>
            <label className={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={pollIsAnonymous}
                onChange={(e) => onChange({ isAnonymous: e.target.checked })}
              />
              <span>Анонимное голосование</span>
            </label>
            {pollIsAnonymous && (
              <div className={styles.anonWarning}>
                При анонимном опросе ответы клиентов не отслеживаются в CRM
              </div>
            )}
            <label className={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={pollAllowsMultiple}
                onChange={(e) => onChange({ allowsMultiple: e.target.checked })}
              />
              <span>Можно выбрать несколько</span>
            </label>
          </div>
        </div>
      )}
    </div>
  )
}
