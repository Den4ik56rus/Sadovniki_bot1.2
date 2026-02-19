// OpenAI Balance Card — карточка баланса OpenAI на дашборде
import { useEffect, useState } from 'react'
import { useOpenAIBalanceStore } from '@/store'
import { useCurrencyStore } from '@/store'
import styles from './OpenAIBalanceCard.module.css'

export function OpenAIBalanceCard() {
  const { balance, isLoading, fetchBalance, updateBudget } = useOpenAIBalanceStore()
  const { usdRate } = useCurrencyStore()
  const [isEditing, setIsEditing] = useState(false)
  const [budgetInput, setBudgetInput] = useState('')

  useEffect(() => {
    fetchBalance()
  }, [fetchBalance])

  const handleSaveBudget = async () => {
    const value = parseFloat(budgetInput)
    if (isNaN(value) || value <= 0) return
    const ok = await updateBudget(value)
    if (ok) setIsEditing(false)
  }

  const handleStartEdit = () => {
    setBudgetInput(balance?.budget_usd?.toString() ?? '')
    setIsEditing(true)
  }

  if (isLoading && !balance) {
    return (
      <div className={styles.card}>
        <div className={styles.loading}>Загрузка данных OpenAI...</div>
      </div>
    )
  }

  if (!balance?.has_admin_key) {
    return (
      <div className={styles.card}>
        <div className={styles.noKey}>
          <span className={styles.noKeyIcon}>🔑</span>
          <span>Добавьте OPENAI_ADMIN_KEY в .env для мониторинга расходов</span>
        </div>
      </div>
    )
  }

  if (balance.error && !balance.total_cost_usd) {
    return (
      <div className={styles.card}>
        <div className={styles.error}>{balance.error}</div>
      </div>
    )
  }

  const totalCostUsd = balance.total_cost_usd
  const totalCostRub = totalCostUsd * usdRate
  const budgetUsd = balance.budget_usd
  const remainingUsd = balance.remaining_usd
  const remainingRub = remainingUsd !== null ? remainingUsd * usdRate : null

  // Определяем статус (зелёный / жёлтый / красный)
  let statusClass = styles.statusOk
  let statusLabel = 'Норма'
  if (budgetUsd !== null && remainingUsd !== null) {
    const percent = (remainingUsd / budgetUsd) * 100
    if (percent <= 10) {
      statusClass = styles.statusCritical
      statusLabel = 'Критично'
    } else if (percent <= 30) {
      statusClass = styles.statusWarning
      statusLabel = 'Внимание'
    }
  }

  // Прогресс-бар: потрачено от бюджета
  const progressPercent = budgetUsd ? Math.min((totalCostUsd / budgetUsd) * 100, 100) : 0

  // Средний дневной расход
  const dailyCosts = balance.daily_costs || []
  const nonZeroDays = dailyCosts.filter(d => d.cost_usd > 0)
  const avgDaily = nonZeroDays.length > 0
    ? nonZeroDays.reduce((sum, d) => sum + d.cost_usd, 0) / nonZeroDays.length
    : 0
  const daysLeft = avgDaily > 0 && remainingUsd !== null
    ? Math.floor(remainingUsd / avgDaily)
    : null

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <h3 className={styles.title}>
          <span className={styles.titleIcon}>🤖</span>
          Баланс OpenAI
        </h3>
        <div className={`${styles.status} ${statusClass}`}>
          {statusLabel}
        </div>
      </div>

      <div className={styles.metricsRow}>
        {/* Потрачено */}
        <div className={styles.metric}>
          <span className={styles.metricLabel}>Потрачено (30 дн.)</span>
          <span className={styles.metricValue}>${totalCostUsd.toFixed(2)}</span>
          <span className={styles.metricSub}>{totalCostRub.toFixed(0)} ₽</span>
        </div>

        {/* Бюджет */}
        <div className={styles.metric}>
          <span className={styles.metricLabel}>Бюджет</span>
          {isEditing ? (
            <div className={styles.editBudget}>
              <input
                type="number"
                step="0.01"
                min="0"
                value={budgetInput}
                onChange={(e) => setBudgetInput(e.target.value)}
                className={styles.budgetInput}
                placeholder="$"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveBudget()
                  if (e.key === 'Escape') setIsEditing(false)
                }}
              />
              <button onClick={handleSaveBudget} className={styles.saveBtn}>✓</button>
              <button onClick={() => setIsEditing(false)} className={styles.cancelBtn}>✕</button>
            </div>
          ) : (
            <span className={styles.metricValue} onClick={handleStartEdit} style={{ cursor: 'pointer' }}>
              {budgetUsd !== null ? `$${budgetUsd.toFixed(2)}` : 'Не задан'}
              <span className={styles.editHint}>✎</span>
            </span>
          )}
          {budgetUsd !== null && (
            <span className={styles.metricSub}>{(budgetUsd * usdRate).toFixed(0)} ₽</span>
          )}
        </div>

        {/* Остаток */}
        <div className={styles.metric}>
          <span className={styles.metricLabel}>Остаток</span>
          <span className={`${styles.metricValue} ${statusClass}`}>
            {remainingUsd !== null ? `$${remainingUsd.toFixed(2)}` : '—'}
          </span>
          {remainingRub !== null && (
            <span className={styles.metricSub}>{remainingRub.toFixed(0)} ₽</span>
          )}
        </div>
      </div>

      {/* Прогресс-бар */}
      {budgetUsd !== null && (
        <div className={styles.progressWrapper}>
          <div className={styles.progressBar}>
            <div
              className={`${styles.progressFill} ${statusClass}`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className={styles.progressLabels}>
            <span>{progressPercent.toFixed(0)}% использовано</span>
            {daysLeft !== null && (
              <span>~{daysLeft} дн. осталось</span>
            )}
          </div>
        </div>
      )}

      {/* Мини-график дневных расходов */}
      {dailyCosts.length > 0 && (
        <div className={styles.sparklineWrapper}>
          <span className={styles.sparklineLabel}>
            Расходы по дням (ср. ${avgDaily.toFixed(2)}/день)
          </span>
          <div className={styles.sparkline}>
            {(() => {
              const maxCost = Math.max(...dailyCosts.map(d => d.cost_usd), 0.01)
              return dailyCosts.map((d, i) => (
                <div
                  key={i}
                  className={styles.sparklineBar}
                  style={{ height: `${Math.max((d.cost_usd / maxCost) * 100, 2)}%` }}
                  title={`${d.date}: $${d.cost_usd.toFixed(4)}`}
                />
              ))
            })()}
          </div>
        </div>
      )}
    </div>
  )
}
