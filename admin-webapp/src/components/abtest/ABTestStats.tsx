import { useEffect } from 'react'
import { useABTestStore } from '@/store'
import styles from './ABTestStats.module.css'

export function ABTestStats() {
  const { stats, loading, fetchStats, selectedTagId, setSelectedTag } = useABTestStore()

  useEffect(() => {
    fetchStats()
  }, [])

  if (loading && !stats) return <div className={styles.loading}>Загрузка...</div>

  const active = stats?.active_variant ?? 'A'
  const stages = stats?.stages ?? []
  const a = stats?.variants.A ?? { users: 0, stages: {}, conversion: 0 }
  const b = stats?.variants.B ?? { users: 0, stages: {}, conversion: 0 }
  const tags = stats?.available_tags ?? []
  const lastStageKey = stages.length > 0 ? stages[stages.length - 1].stage_key : null
  const lastStageTitle = stages.length > 0 ? stages[stages.length - 1].title : 'Оплатили'

  return (
    <div className={styles.section}>
      <h3 className={styles.title}>A/B тест воронок</h3>

      {tags.length > 0 && (
        <div className={styles.filterRow}>
          <select
            className={styles.tagSelect}
            value={selectedTagId ?? ''}
            onChange={e => setSelectedTag(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Все пользователи</option>
            {tags.map(t => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
          {selectedTagId && (
            <button className={styles.clearFilter} onClick={() => setSelectedTag(null)}>
              Сбросить
            </button>
          )}
        </div>
      )}

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
