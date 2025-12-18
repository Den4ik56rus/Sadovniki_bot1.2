// Expense Stats - 3 horizontal cards: Denis total, Danil total, Period change

import { useExpenseStore } from '@/store/expenseStore'
import styles from './ExpenseStats.module.css'

export function ExpenseStats() {
  const { stats, isLoadingStats } = useExpenseStore()

  // Format number as currency
  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Math.abs(amount))
  }

  if (isLoadingStats || !stats) {
    return (
      <div className={styles.statsContainer}>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Денис</span>
          <span className={styles.statValueLoading}>Загрузка...</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Данил</span>
          <span className={styles.statValueLoading}>Загрузка...</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Изменение за период</span>
          <span className={styles.statValueLoading}>Загрузка...</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Всего расходов</span>
          <span className={styles.statValueLoading}>Загрузка...</span>
        </div>
      </div>
    )
  }

  // Get amounts by paid_by
  const denisData = stats.by_paid_by.find(p => p.paid_by === 'Денис')
  const danilData = stats.by_paid_by.find(p => p.paid_by === 'Данил')

  const denisAmount = denisData?.amount ?? 0
  const danilAmount = danilData?.amount ?? 0

  return (
    <div className={styles.statsContainer}>
      {/* Denis Total */}
      <div className={styles.statCard}>
        <span className={styles.statLabel}>Денис</span>
        <span className={`${styles.statValue} ${styles.neutral}`}>
          {formatAmount(denisAmount)}
          <span className={styles.currency}>RUB</span>
        </span>
      </div>

      {/* Danil Total */}
      <div className={styles.statCard}>
        <span className={styles.statLabel}>Данил</span>
        <span className={`${styles.statValue} ${styles.neutral}`}>
          {formatAmount(danilAmount)}
          <span className={styles.currency}>RUB</span>
        </span>
      </div>

      {/* Period Change - total of all expenses */}
      <div className={styles.statCard}>
        <span className={styles.statLabel}>Изменение за период</span>
        <span className={`${styles.statValue} ${styles.neutral}`}>
          {formatAmount(stats.total_amount)}
          <span className={styles.currency}>RUB</span>
        </span>
      </div>

      {/* Total Expenses */}
      <div className={styles.statCard}>
        <span className={styles.statLabel}>Всего расходов</span>
        <span className={`${styles.statValue} ${styles.neutral}`}>
          {formatAmount(stats.total_amount)}
          <span className={styles.currency}>RUB</span>
        </span>
      </div>
    </div>
  )
}
