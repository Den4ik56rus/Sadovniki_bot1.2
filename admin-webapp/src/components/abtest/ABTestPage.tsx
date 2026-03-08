import { useEffect } from 'react'
import { useABTestStore } from '@/store'
import styles from './ABTestPage.module.css'

export function ABTestPage() {
  const { stats, loading, fetchStats, setVariant, selectedTagId, setSelectedTag } = useABTestStore()

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

  if (loading && !stats) {
    return <div className={styles.loading}>Загрузка...</div>
  }

  const active = stats?.active_variant ?? 'A'
  const stages = stats?.stages ?? []
  const a = stats?.variants.A ?? { users: 0, stages: {}, conversion: 0 }
  const b = stats?.variants.B ?? { users: 0, stages: {}, conversion: 0 }
  const tags = stats?.available_tags ?? []

  const getPercent = (count: number, total: number) =>
    total > 0 ? Math.round((count / total) * 100) : 0

  const winnerVariant = a.conversion >= b.conversion ? 'A' : 'B'

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>A/B тест воронок</h1>
        <div className={styles.toggle}>
          <span className={styles.toggleLabel}>Воронка для новых:</span>
          <div className={styles.toggleButtons}>
            <button
              className={`${styles.toggleBtn} ${active === 'A' ? styles.active : ''}`}
              onClick={() => handleSwitch('A')}
            >
              Тип А
            </button>
            <button
              className={`${styles.toggleBtn} ${active === 'B' ? styles.active : ''}`}
              onClick={() => handleSwitch('B')}
            >
              Тип Б
            </button>
          </div>
        </div>
      </div>

      {/* Tag filter */}
      {tags.length > 0 && (
        <div className={styles.filterRow}>
          <span className={styles.filterLabel}>Сегмент:</span>
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

      {/* Summary cards */}
      <div className={styles.summaryRow}>
        {(['A', 'B'] as const).map((variant) => {
          const v = variant === 'A' ? a : b
          const isWinner = winnerVariant === variant && (a.users > 0 || b.users > 0)
          return (
            <div
              key={variant}
              className={`${styles.summaryCard} ${isWinner ? styles.winner : ''}`}
            >
              <div className={styles.summaryVariant}>
                Тип {variant} {active === variant && '●'}
              </div>
              <div className={styles.summaryConversion}>
                {v.conversion}<span className={styles.summaryUnit}>%</span>
              </div>
              <div className={styles.summaryUsers}>{v.users} пользователей</div>
              {isWinner && <div className={styles.winnerBadge}>Лидирует</div>}
            </div>
          )
        })}
      </div>

      {/* Funnel table */}
      <div className={styles.funnelCard}>
        <table className={styles.funnelTable}>
          <thead>
            <tr className={styles.stageHeaderRow}>
              <th />
              <th>
                <div className={styles.stageHeader} style={{ background: '#6B7280' }}>
                  Всего
                </div>
              </th>
              {stages.map((stage) => (
                <th key={stage.stage_key}>
                  <div
                    className={styles.stageHeader}
                    style={{ background: stage.color }}
                  >
                    {stage.title}
                  </div>
                </th>
              ))}
              <th>
                <div className={styles.stageHeader} style={{ background: '#4A7C59' }}>
                  Конверсия
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            {(['A', 'B'] as const).map((variant) => {
              const v = variant === 'A' ? a : b
              return (
                <tr
                  key={variant}
                  className={`${styles.variantRow} ${active === variant ? styles.activeVariant : ''}`}
                >
                  <td className={styles.variantLabel}>
                    Тип {variant}
                    {active === variant && <span className={styles.activeDot} />}
                  </td>
                  <td className={styles.stageCell}>
                    <span className={styles.stageCount}>{v.users}</span>
                    <span className={styles.stageCountLabel}>чел.</span>
                  </td>
                  {stages.map((stage) => {
                    const count = v.stages[stage.stage_key] ?? 0
                    const pct = getPercent(count, v.users)
                    return (
                      <td key={stage.stage_key} className={styles.stageCell}>
                        <span className={styles.stageCount}>{count}</span>
                        <span className={styles.stageCountLabel}>чел.</span>
                        <div className={styles.progressWrap}>
                          <div
                            className={styles.progressBar}
                            style={{
                              width: `${pct}%`,
                              background: stage.color,
                            }}
                          />
                        </div>
                        <span className={styles.progressPercent}>{pct}%</span>
                      </td>
                    )
                  })}
                  <td className={styles.conversionCell}>
                    <span
                      className={styles.conversionValue}
                      style={{ color: '#22C55E' }}
                    >
                      {v.conversion}%
                    </span>
                    <span className={styles.conversionLabel}>конверсия</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
