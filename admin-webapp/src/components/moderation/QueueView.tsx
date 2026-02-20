import { useModerationStore } from '@/store/moderationStore'
import { QueueList } from './QueueList'
import { QueueItemDetail } from './QueueItemDetail'
import styles from './QueueView.module.css'

export function QueueView() {
  const { selectedItem } = useModerationStore()

  return (
    <div className={styles.splitPane}>
      <div className={styles.listPane}>
        <QueueList />
      </div>
      <div className={styles.detailPane}>
        {selectedItem ? (
          <QueueItemDetail />
        ) : (
          <div className={styles.emptyDetail}>
            <div className={styles.emptyIcon}>
              <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                <path d="M24 4L6 12V22C6 33.1 13.8 43.2 24 46C34.2 43.2 42 33.1 42 22V12L24 4Z" stroke="currentColor" strokeWidth="2" strokeOpacity="0.3" strokeLinejoin="round"/>
                <path d="M16 24L22 30L32 18" stroke="currentColor" strokeWidth="2" strokeOpacity="0.3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <p>Выберите запись для просмотра</p>
          </div>
        )}
      </div>
    </div>
  )
}
