import { useEffect } from 'react'
import { useABTestStore } from '@/store'
import styles from './ABTestToggle.module.css'

export function ABTestToggle() {
  const { stats, loading, fetchStats, setVariant } = useABTestStore()

  useEffect(() => {
    fetchStats()
  }, [])

  const handleSwitch = async (variant: 'A' | 'B') => {
    if (stats?.active_variant === variant) return
    const label = variant === 'B' ? 'Тип Б' : 'Тип А'
    const confirmed = window.confirm(
      `Все новые пользователи будут получать ${label}. Продолжить?`
    )
    if (!confirmed) return
    await setVariant(variant)
    await fetchStats()
  }

  const active = stats?.active_variant ?? 'A'

  return (
    <div className={styles.section}>
      <div className={styles.info}>
        <span className={styles.label}>Воронка для новых пользователей</span>
        <span className={styles.description}>
          Все новые пользователи попадают в выбранный вариант воронки
        </span>
      </div>
      <div className={styles.buttons}>
        <button
          className={`${styles.btn} ${active === 'A' ? styles.active : ''}`}
          onClick={() => handleSwitch('A')}
          disabled={loading}
        >
          Тип А
        </button>
        <button
          className={`${styles.btn} ${active === 'B' ? styles.active : ''}`}
          onClick={() => handleSwitch('B')}
          disabled={loading}
        >
          Тип Б
        </button>
      </div>
    </div>
  )
}
