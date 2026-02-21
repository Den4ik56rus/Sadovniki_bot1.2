// Broadcast Page — управление рассылками

import { useEffect, useState } from 'react'
import { useBroadcastStore } from '@/store/broadcastStore'
import { BroadcastList } from './BroadcastList'
import { BroadcastForm } from './BroadcastForm'
import { BroadcastDetail } from './BroadcastDetail'
import styles from './BroadcastPage.module.css'

type Mode = 'list' | 'create' | 'edit'

export function BroadcastPage() {
  const {
    currentBroadcast,
    fetchBroadcasts,
    selectBroadcast,
    error,
    clearError,
  } = useBroadcastStore()

  const [mode, setMode] = useState<Mode>('list')

  useEffect(() => {
    fetchBroadcasts()
  }, [fetchBroadcasts])

  const handleCreate = () => {
    selectBroadcast(null)
    setMode('create')
  }

  const handleEdit = () => {
    setMode('edit')
  }

  const handleBack = () => {
    setMode('list')
    selectBroadcast(null)
  }

  const handleSaved = () => {
    setMode('list')
    fetchBroadcasts()
  }

  const handleSelected = () => {
    setMode('list')
  }

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h2>Рассылки</h2>
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
            Новая рассылка
          </button>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className={styles.errorBanner}>
          <span>{error}</span>
          <button className={styles.errorClose} onClick={clearError}>✕</button>
        </div>
      )}

      {/* Content */}
      {mode === 'create' || mode === 'edit' ? (
        <BroadcastForm
          broadcast={mode === 'edit' ? currentBroadcast : null}
          onSaved={handleSaved}
          onCancel={handleBack}
        />
      ) : (
        <div className={styles.columns}>
          <div className={styles.leftColumn}>
            <BroadcastList onSelected={handleSelected} />
          </div>
          {currentBroadcast && (
            <div className={styles.rightColumn}>
              <BroadcastDetail onEdit={handleEdit} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
