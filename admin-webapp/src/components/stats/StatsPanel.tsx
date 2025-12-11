import { useEffect } from 'react'
import { useStatsStore, useCurrencyStore } from '@/store'
import styles from './StatsPanel.module.css'

export function StatsPanel() {
  const { stats, embeddingStats, period, isLoading, error, fetchStats, fetchEmbeddingStats, setPeriod } = useStatsStore()
  const { usdRate, fetchRate } = useCurrencyStore()

  useEffect(() => {
    fetchStats(period)
    fetchEmbeddingStats(period)
    fetchRate()
  }, [period, fetchStats, fetchEmbeddingStats, fetchRate])

  // Convert USD to RUB
  const toRub = (usd: number) => (usd * usdRate).toFixed(2)

  const handlePeriodChange = (newPeriod: 'day' | 'week' | 'month' | 'all') => {
    setPeriod(newPeriod)
  }

  if (error) {
    return <div className={styles.error}>Ошибка: {error}</div>
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2>Статистика</h2>
        <div className={styles.periodSelector}>
          {(['day', 'week', 'month', 'all'] as const).map((p) => (
            <button
              key={p}
              className={`${styles.periodButton} ${period === p ? styles.active : ''}`}
              onClick={() => handlePeriodChange(p)}
            >
              {p === 'day' && 'День'}
              {p === 'week' && 'Неделя'}
              {p === 'month' && 'Месяц'}
              {p === 'all' && 'Всё время'}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className={styles.loading}>Загрузка...</div>
      ) : stats ? (
        <div className={styles.content}>
          {/* Overview Cards */}
          <div className={styles.cards}>
            <div className={styles.card}>
              <div className={styles.cardValue}>
                {stats.overview.total_consultations.toLocaleString()}
              </div>
              <div className={styles.cardLabel}>Консультаций</div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardValue}>
                {stats.overview.total_tokens.toLocaleString()}
              </div>
              <div className={styles.cardLabel}>Токенов LLM</div>
            </div>
            <div
              className={`${styles.card} ${styles.highlight}`}
              title={`$${stats.overview.total_cost_usd.toFixed(4)}`}
            >
              <div className={styles.cardValue}>
                {toRub(stats.overview.total_cost_usd)} ₽
              </div>
              <div className={styles.cardLabel}>Стоимость LLM</div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardValue}>
                {stats.overview.avg_latency_ms.toLocaleString()}ms
              </div>
              <div className={styles.cardLabel}>Ср. задержка</div>
            </div>
          </div>

          {/* Embeddings Stats */}
          {embeddingStats && (
            <div className={styles.section}>
              <h3>Embeddings</h3>
              <div className={styles.embeddingStats}>
                <div className={styles.embeddingRow}>
                  <span className={styles.embeddingLabel}>Документы:</span>
                  <span className={styles.embeddingTokens}>
                    {embeddingStats.documents.tokens.toLocaleString()} токенов
                  </span>
                  <span
                    className={styles.embeddingCost}
                    title={`$${embeddingStats.documents.cost_usd.toFixed(6)}`}
                  >
                    {toRub(embeddingStats.documents.cost_usd)} ₽
                  </span>
                </div>
                <div className={styles.embeddingRow}>
                  <span className={styles.embeddingLabel}>Консультации:</span>
                  <span className={styles.embeddingTokens}>
                    {embeddingStats.consultations.tokens.toLocaleString()} токенов
                  </span>
                  <span
                    className={styles.embeddingCost}
                    title={`$${embeddingStats.consultations.cost_usd.toFixed(6)}`}
                  >
                    {toRub(embeddingStats.consultations.cost_usd)} ₽
                  </span>
                </div>
                <div className={`${styles.embeddingRow} ${styles.embeddingTotal}`}>
                  <span className={styles.embeddingLabel}>Всего:</span>
                  <span className={styles.embeddingTokens}>
                    {embeddingStats.total.tokens.toLocaleString()} токенов
                  </span>
                  <span
                    className={styles.embeddingCost}
                    title={`$${embeddingStats.total.cost_usd.toFixed(6)}`}
                  >
                    {toRub(embeddingStats.total.cost_usd)} ₽
                  </span>
                </div>

                {/* By Model */}
                {embeddingStats.by_model.length > 0 && (
                  <div className={styles.byModel}>
                    <div className={styles.byModelTitle}>По моделям:</div>
                    {embeddingStats.by_model.map((item) => (
                      <div key={item.model} className={styles.modelRow}>
                        <span className={styles.modelName}>{item.model}</span>
                        <span
                          className={styles.modelCost}
                          title={`$${item.total_cost_usd.toFixed(6)}`}
                        >
                          {toRub(item.total_cost_usd)} ₽
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Today Stats */}
          <div className={styles.section}>
            <h3>Сегодня</h3>
            <div className={styles.todayStats}>
              <div className={styles.todayStat}>
                <span className={styles.todayValue}>{stats.today.consultations}</span>
                <span className={styles.todayLabel}>консультаций</span>
              </div>
              <div className={styles.todayStat}>
                <span className={styles.todayValue}>{stats.today.tokens.toLocaleString()}</span>
                <span className={styles.todayLabel}>токенов</span>
              </div>
              <div className={styles.todayStat} title={`$${stats.today.cost_usd.toFixed(4)}`}>
                <span className={`${styles.todayValue} ${styles.cost}`}>
                  {toRub(stats.today.cost_usd)} ₽
                </span>
                <span className={styles.todayLabel}>стоимость</span>
              </div>
            </div>
          </div>

          {/* By Culture */}
          {stats.by_culture.length > 0 && (
            <div className={styles.section}>
              <h3>По культурам</h3>
              <div className={styles.barChart}>
                {stats.by_culture.map((item) => {
                  const maxCount = Math.max(...stats.by_culture.map((c) => c.count))
                  const width = (item.count / maxCount) * 100
                  return (
                    <div key={item.culture} className={styles.barRow}>
                      <span className={styles.barLabel}>{item.culture}</span>
                      <div className={styles.barContainer}>
                        <div
                          className={styles.bar}
                          style={{ width: `${width}%` }}
                        />
                      </div>
                      <span className={styles.barValue}>{item.count}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* By Category */}
          {stats.by_category.length > 0 && (
            <div className={styles.section}>
              <h3>По категориям</h3>
              <div className={styles.barChart}>
                {stats.by_category.map((item) => {
                  const maxCount = Math.max(...stats.by_category.map((c) => c.count))
                  const width = (item.count / maxCount) * 100
                  return (
                    <div key={item.category} className={styles.barRow}>
                      <span className={styles.barLabel}>{item.category}</span>
                      <div className={styles.barContainer}>
                        <div
                          className={`${styles.bar} ${styles.barCategory}`}
                          style={{ width: `${width}%` }}
                        />
                      </div>
                      <span className={styles.barValue}>{item.count}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
