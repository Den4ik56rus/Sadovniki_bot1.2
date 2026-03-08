import { useEffect } from 'react'
import { useABTestStore } from '@/store'
import styles from './ABTestSection.module.css'

export function ABTestSection() {
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

  if (loading && !stats) return <div className={styles.loading}>Загрузка...</div>

  const active = stats?.active_variant ?? 'A'
  const stages = stats?.stages ?? []
  const a = stats?.variants.A ?? { users: 0, stages: {}, conversion: 0 }
  const b = stats?.variants.B ?? { users: 0, stages: {}, conversion: 0 }
  const lastStageKey = stages.length > 0 ? stages[stages.length - 1].stage_key : null
  const lastStageTitle = stages.length > 0 ? stages[stages.length - 1].title : 'Оплатили'

  return (
    <div className={styles.section}>
      <h3 className={styles.title}>A/B тест воронок</h3>

      <div className={styles.toggle}>
        <span className={styles.label}>Воронка для новых пользователей:</span>
        <div className={styles.buttons}>
          <button
            className={`${styles.btn} ${active === 'A' ? styles.active : ''}`}
            onClick={() => handleSwitch('A')}
          >
            Тип А
          </button>
          <button
            className={`${styles.btn} ${active === 'B' ? styles.active : ''}`}
            onClick={() => handleSwitch('B')}
          >
            Тип Б
          </button>
        </div>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th></th>
            <th>Тип А {active === 'A' && '●'}</th>
            <th>Тип Б {active === 'B' && '●'}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Пользователей</td>
            <td>{a.users}</td>
            <td>{b.users}</td>
          </tr>
          <tr>
            <td>{lastStageTitle}</td>
            <td>{lastStageKey ? (a.stages[lastStageKey] ?? 0) : 0}</td>
            <td>{lastStageKey ? (b.stages[lastStageKey] ?? 0) : 0}</td>
          </tr>
          <tr className={styles.highlight}>
            <td>Конверсия</td>
            <td>{a.conversion}%</td>
            <td>{b.conversion}%</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
