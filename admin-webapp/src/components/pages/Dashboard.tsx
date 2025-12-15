// Dashboard Page - Рабочий стол с основной статистикой
import { useEffect } from 'react'
import { useStatsStore, useCrmStore, useCurrencyStore } from '@/store'
import styles from './Dashboard.module.css'

export function Dashboard() {
  const { stats, embeddingStats, period, fetchStats, fetchEmbeddingStats, setPeriod } = useStatsStore()
  const { stats: crmStats, fetchClients } = useCrmStore()
  const { usdRate, fetchRate } = useCurrencyStore()

  useEffect(() => {
    fetchStats(period)
    fetchEmbeddingStats(period)
    fetchClients()
    fetchRate()
  }, [fetchStats, fetchEmbeddingStats, fetchClients, fetchRate, period])

  const totalClients = Object.values(crmStats).reduce((a, b) => (a ?? 0) + (b ?? 0), 0)
  const paidClients = crmStats.paid || 0

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>Рабочий стол</h1>
        <div className={styles.periodSelector}>
          {(['day', 'week', 'month', 'all'] as const).map((p) => (
            <button
              key={p}
              className={`${styles.periodButton} ${period === p ? styles.active : ''}`}
              onClick={() => setPeriod(p)}
            >
              {p === 'day' ? 'День' : p === 'week' ? 'Неделя' : p === 'month' ? 'Месяц' : 'Всё время'}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.grid}>
        {/* Основные метрики */}
        <div className={styles.card}>
          <div className={styles.cardIcon}>💼</div>
          <div className={styles.cardContent}>
            <span className={styles.cardValue}>{totalClients}</span>
            <span className={styles.cardLabel}>Всего клиентов</span>
          </div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardIcon}>💰</div>
          <div className={styles.cardContent}>
            <span className={styles.cardValue}>{paidClients}</span>
            <span className={styles.cardLabel}>Оплатили</span>
          </div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardIcon}>💬</div>
          <div className={styles.cardContent}>
            <span className={styles.cardValue}>{stats?.overview?.total_consultations ?? 0}</span>
            <span className={styles.cardLabel}>Консультаций</span>
          </div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardIcon}>⚡</div>
          <div className={styles.cardContent}>
            <span className={styles.cardValue}>{stats?.today?.consultations ?? 0}</span>
            <span className={styles.cardLabel}>Сегодня</span>
          </div>
        </div>

        {/* Финансы */}
        <div className={`${styles.card} ${styles.wide}`}>
          <div className={styles.cardIcon}>💵</div>
          <div className={styles.cardContent}>
            <span className={styles.cardValue}>
              {((stats?.overview?.total_cost_usd ?? 0) * usdRate).toFixed(0)} ₽
            </span>
            <span className={styles.cardLabel}>Расходы на AI</span>
          </div>
          <div className={styles.cardSubtext}>
            ${(stats?.overview?.total_cost_usd ?? 0).toFixed(2)} USD
          </div>
        </div>

        <div className={`${styles.card} ${styles.wide}`}>
          <div className={styles.cardIcon}>🔤</div>
          <div className={styles.cardContent}>
            <span className={styles.cardValue}>
              {((stats?.overview?.total_tokens ?? 0) / 1000).toFixed(1)}K
            </span>
            <span className={styles.cardLabel}>Токенов использовано</span>
          </div>
        </div>

        {/* Воронка */}
        <div className={`${styles.card} ${styles.full}`}>
          <h3 className={styles.sectionTitle}>Воронка продаж</h3>
          <div className={styles.funnel}>
            <div className={styles.funnelItem}>
              <div className={styles.funnelBar} style={{ width: '100%', background: 'var(--accent-blue)' }} />
              <span className={styles.funnelLabel}>Новые</span>
              <span className={styles.funnelValue}>{crmStats.new || 0}</span>
            </div>
            <div className={styles.funnelItem}>
              <div
                className={styles.funnelBar}
                style={{
                  width: totalClients ? `${((crmStats.tried || 0) / totalClients) * 100}%` : '0%',
                  background: 'var(--accent-purple)'
                }}
              />
              <span className={styles.funnelLabel}>Попробовали</span>
              <span className={styles.funnelValue}>{crmStats.tried || 0}</span>
            </div>
            <div className={styles.funnelItem}>
              <div
                className={styles.funnelBar}
                style={{
                  width: totalClients ? `${((crmStats.trial_ended || 0) / totalClients) * 100}%` : '0%',
                  background: 'var(--accent-yellow)'
                }}
              />
              <span className={styles.funnelLabel}>Триал закончился</span>
              <span className={styles.funnelValue}>{crmStats.trial_ended || 0}</span>
            </div>
            <div className={styles.funnelItem}>
              <div
                className={styles.funnelBar}
                style={{
                  width: totalClients ? `${((crmStats.paid || 0) / totalClients) * 100}%` : '0%',
                  background: 'var(--accent-green)'
                }}
              />
              <span className={styles.funnelLabel}>Оплатили</span>
              <span className={styles.funnelValue}>{crmStats.paid || 0}</span>
            </div>
          </div>
        </div>

        {/* Статистика по культурам */}
        {stats?.by_culture && stats.by_culture.length > 0 && (
          <div className={`${styles.card} ${styles.half}`}>
            <h3 className={styles.sectionTitle}>По культурам</h3>
            <div className={styles.list}>
              {stats.by_culture.slice(0, 5).map((item) => (
                <div key={item.culture} className={styles.listItem}>
                  <span className={styles.listLabel}>{item.culture || 'Не указано'}</span>
                  <span className={styles.listValue}>{item.count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Статистика по категориям */}
        {stats?.by_category && stats.by_category.length > 0 && (
          <div className={`${styles.card} ${styles.half}`}>
            <h3 className={styles.sectionTitle}>По категориям</h3>
            <div className={styles.list}>
              {stats.by_category.slice(0, 5).map((item) => (
                <div key={item.category} className={styles.listItem}>
                  <span className={styles.listLabel}>{item.category || 'Не указано'}</span>
                  <span className={styles.listValue}>{item.count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Embeddings */}
        {embeddingStats && (
          <div className={`${styles.card} ${styles.full}`}>
            <h3 className={styles.sectionTitle}>Расходы на Embeddings</h3>
            <div className={styles.embeddingGrid}>
              <div className={styles.embeddingItem}>
                <span className={styles.embeddingLabel}>Консультации</span>
                <span className={styles.embeddingValue}>
                  {(embeddingStats.consultations.cost_usd * usdRate).toFixed(0)} ₽
                </span>
              </div>
              <div className={styles.embeddingItem}>
                <span className={styles.embeddingLabel}>Документы</span>
                <span className={styles.embeddingValue}>
                  {(embeddingStats.documents.cost_usd * usdRate).toFixed(0)} ₽
                </span>
              </div>
              <div className={styles.embeddingItem}>
                <span className={styles.embeddingLabel}>Всего</span>
                <span className={styles.embeddingValue}>
                  {(embeddingStats.total.cost_usd * usdRate).toFixed(0)} ₽
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
