import { useEffect } from 'react'
import { useModerationStore } from '@/store/moderationStore'
import { QueueView } from './QueueView'
import { KBBrowser } from './KBBrowser'
import styles from './ModerationPage.module.css'

export function ModerationPage() {
  const { activeTab, setActiveTab, pendingCount, fetchQueue, fetchStats } = useModerationStore()

  useEffect(() => {
    fetchQueue()
    fetchStats()
  }, [fetchQueue, fetchStats])

  return (
    <div className={styles.page}>
      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'queue' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('queue')}
        >
          Очередь
          {pendingCount > 0 && <span className={styles.badge}>{pendingCount}</span>}
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'kb' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('kb')}
        >
          База знаний
        </button>
      </div>

      <div className={styles.content}>
        {activeTab === 'queue' ? <QueueView /> : <KBBrowser />}
      </div>
    </div>
  )
}
