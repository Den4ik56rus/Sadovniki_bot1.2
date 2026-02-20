import { useModerationStore } from '@/store/moderationStore'
import type { ModerationStatus } from '@/types'
import styles from './QueueList.module.css'

const STATUS_TABS: { key: ModerationStatus | 'all'; label: string }[] = [
  { key: 'pending', label: 'Ожидающие' },
  { key: 'approved', label: 'Одобренные' },
  { key: 'rejected', label: 'Отклонённые' },
  { key: 'all', label: 'Все' },
]

function timeAgo(dateStr: string): string {
  const now = Date.now()
  const d = new Date(dateStr).getTime()
  const diff = Math.floor((now - d) / 1000)
  if (diff < 60) return 'только что'
  if (diff < 3600) return `${Math.floor(diff / 60)} мин`
  if (diff < 86400) return `${Math.floor(diff / 3600)} ч`
  return `${Math.floor(diff / 86400)} дн`
}

export function QueueList() {
  const {
    items, total, isLoading, statusFilter, currentPage,
    selectedItemId, setStatusFilter, setPage, selectItem,
  } = useModerationStore()

  const pageSize = 30
  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className={styles.list}>
      {/* Status filter tabs */}
      <div className={styles.filterTabs}>
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key}
            className={`${styles.filterTab} ${statusFilter === tab.key ? styles.filterTabActive : ''}`}
            onClick={() => setStatusFilter(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Count */}
      <div className={styles.countRow}>
        {isLoading ? 'Загрузка...' : `${total} записей`}
      </div>

      {/* Items */}
      <div className={styles.items}>
        {items.map((item) => (
          <button
            key={item.id}
            className={`${styles.card} ${selectedItemId === item.id ? styles.cardActive : ''}`}
            onClick={() => selectItem(item.id)}
          >
            <div className={styles.cardHeader}>
              <span className={styles.cardId}>#{item.id}</span>
              <span className={styles.cardTime}>{timeAgo(item.created_at)}</span>
            </div>
            <div className={styles.cardQuestion}>
              {(item.question || '').slice(0, 90)}
              {(item.question || '').length > 90 ? '...' : ''}
            </div>
            <div className={styles.cardMeta}>
              {item.category_guess ? (
                <span className={styles.categoryTag}>{item.category_guess}</span>
              ) : (
                <span className={styles.categoryMissing}>без категории</span>
              )}
              {item.username && (
                <span className={styles.cardUser}>@{item.username}</span>
              )}
            </div>
          </button>
        ))}

        {!isLoading && items.length === 0 && (
          <div className={styles.empty}>Нет записей</div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button
            disabled={currentPage === 0}
            onClick={() => setPage(currentPage - 1)}
            className={styles.pageBtn}
          >
            &larr;
          </button>
          <span className={styles.pageInfo}>
            {currentPage + 1} / {totalPages}
          </span>
          <button
            disabled={currentPage >= totalPages - 1}
            onClick={() => setPage(currentPage + 1)}
            className={styles.pageBtn}
          >
            &rarr;
          </button>
        </div>
      )}
    </div>
  )
}
