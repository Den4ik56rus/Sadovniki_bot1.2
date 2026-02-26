// TriggersPage — split-panel: list + editor/log (follows BroadcastPage pattern)

import { useEffect, useState } from 'react'
import { useTriggerStore } from '@/store/triggerStore'
import { useFunnelStore } from '@/store/funnelStore'
import { TriggerList } from './TriggerList'
import { TriggerEditor } from './TriggerEditor'
import { TriggerLogView } from './TriggerLogView'
import styles from './TriggersPage.module.css'

type Mode = 'list' | 'create' | 'edit'

export function TriggersPage() {
  const {
    currentTrigger,
    fetchTriggers,
    setCurrentTrigger,
    error,
  } = useTriggerStore()
  const { fetchFunnels } = useFunnelStore()

  const [mode, setMode] = useState<Mode>('list')
  const [errorDismissed, setErrorDismissed] = useState(false)

  useEffect(() => {
    fetchTriggers()
    fetchFunnels()
  }, [fetchTriggers, fetchFunnels])

  const handleCreate = () => {
    setCurrentTrigger(null)
    setMode('create')
  }

  const handleEdit = () => {
    setMode('edit')
  }

  const handleBack = () => {
    setMode('list')
    setCurrentTrigger(null)
  }

  const handleSaved = () => {
    setMode('list')
    fetchTriggers()
  }

  const handleSelected = () => {
    setMode('list')
  }

  const showError = error && !errorDismissed

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h2>Триггеры</h2>
          {(mode === 'create' || mode === 'edit') && (
            <button className={styles.backButton} onClick={handleBack}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M9 2L4 7L9 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Назад
            </button>
          )}
        </div>
        {mode === 'list' && (
          <button className={styles.addButton} onClick={handleCreate}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 1V13M1 7H13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            Новый триггер
          </button>
        )}
      </div>

      {/* Error banner */}
      {showError && (
        <div className={styles.errorBanner}>
          <span>{error}</span>
          <button className={styles.errorClose} onClick={() => setErrorDismissed(true)}>&#10005;</button>
        </div>
      )}

      {/* Content */}
      {mode === 'create' || mode === 'edit' ? (
        <div style={{ maxWidth: '680px' }}>
          <TriggerEditor
            trigger={mode === 'edit' ? currentTrigger : null}
            onSaved={handleSaved}
            onCancel={handleBack}
          />
        </div>
      ) : (
        <div className={styles.columns}>
          <div className={styles.leftColumn}>
            <TriggerList onSelected={handleSelected} />
          </div>
          {currentTrigger && (
            <div className={styles.rightColumn}>
              <TriggerLogView trigger={currentTrigger} onEdit={handleEdit} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
