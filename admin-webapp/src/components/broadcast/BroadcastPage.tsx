// Broadcast Page — управление рассылками

import { useEffect, useState } from 'react'
import { useBroadcastStore } from '@/store/broadcastStore'
import { BroadcastList } from './BroadcastList'
import { BroadcastForm } from './BroadcastForm'
import { BroadcastDetail } from './BroadcastDetail'
import { QuizBroadcastForm } from './QuizBroadcastForm'
import styles from './BroadcastPage.module.css'

type Mode = 'list' | 'create' | 'edit'
type Tab = 'broadcasts' | 'quiz'

export function BroadcastPage() {
  const {
    broadcasts,
    currentBroadcast,
    selectedIds,
    fetchBroadcasts,
    selectBroadcast,
    deleteBroadcastsBulk,
    selectAll,
    clearSelection,
    error,
    clearError,
  } = useBroadcastStore()

  const [mode, setMode] = useState<Mode>('list')
  const [activeTab, setActiveTab] = useState<Tab>('broadcasts')

  useEffect(() => {
    fetchBroadcasts()
  }, [fetchBroadcasts])

  const handleCreate = () => {
    selectBroadcast(null)
    clearSelection()
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

  const handleBulkDelete = async () => {
    const count = selectedIds.size
    if (!confirm(`Удалить ${count} рассылок?`)) return
    await deleteBroadcastsBulk()
  }

  const handleSelectAll = () => {
    const deletable = broadcasts.filter((b) => b.status !== 'sending')
    if (selectedIds.size === deletable.length) {
      clearSelection()
    } else {
      selectAll()
    }
  }

  const hasSelection = selectedIds.size > 0
  const allSelected = broadcasts.length > 0 && selectedIds.size === broadcasts.filter((b) => b.status !== 'sending').length

  return (
    <div className={styles.container}>
      {/* Tabs */}
      <div className={styles.tabBar}>
        <button
          className={`${styles.tabButton} ${activeTab === 'broadcasts' ? styles.tabActive : ''}`}
          onClick={() => { setActiveTab('broadcasts'); setMode('list') }}
        >
          Рассылки
        </button>
        <button
          className={`${styles.tabButton} ${activeTab === 'quiz' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('quiz')}
        >
          Квиз-рассылка
        </button>
      </div>

      {activeTab === 'quiz' ? (
        <QuizBroadcastForm />
      ) : (
      <>
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

      {/* Selection toolbar */}
      {mode === 'list' && hasSelection && (
        <div className={styles.selectionBar}>
          <div className={styles.selectionInfo}>
            <div
              className={`${styles.selectAllCheckbox} ${allSelected ? styles.selectAllChecked : ''}`}
              onClick={handleSelectAll}
            >
              {allSelected && (
                <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                  <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              )}
            </div>
            <span>Выбрано: {selectedIds.size}</span>
          </div>
          <div className={styles.selectionActions}>
            <button className={styles.selectionCancel} onClick={clearSelection}>
              Отменить
            </button>
            <button className={styles.selectionDelete} onClick={handleBulkDelete}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M2 4H12M5 4V2.5C5 2.22 5.22 2 5.5 2H8.5C8.78 2 9 2.22 9 2.5V4M11 4V11.5C11 11.78 10.78 12 10.5 12H3.5C3.22 12 3 11.78 3 11.5V4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Удалить ({selectedIds.size})
            </button>
          </div>
        </div>
      )}

      {/* Select all toggle when no selection */}
      {mode === 'list' && !hasSelection && broadcasts.length > 1 && (
        <div className={styles.selectAllRow}>
          <button className={styles.selectAllButton} onClick={selectAll}>
            Выбрать все
          </button>
        </div>
      )}

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
      </>
      )}
    </div>
  )
}
