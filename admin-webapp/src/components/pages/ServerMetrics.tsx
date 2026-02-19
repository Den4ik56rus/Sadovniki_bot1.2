// ServerMetrics — Мониторинг сервера на дашборде
import { useEffect, useState, useCallback } from 'react'
import { api } from '@/services/api'
import type { ServerMetrics as ServerMetricsType, MetricsHistoryPoint } from '@/types'
import styles from './ServerMetrics.module.css'

// SVG Sparkline — мини-график
function Sparkline({
  data,
  color,
  height = 40,
  width = 200,
}: {
  data: number[]
  color: string
  height?: number
  width?: number
}) {
  if (data.length < 2) return null

  const max = Math.max(...data, 1)
  const min = Math.min(...data, 0)
  const range = max - min || 1

  // Оставляем отступ сверху для линии, снизу — мягкий fade
  const paddingTop = 4
  const chartHeight = height - paddingTop

  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width
    const y = paddingTop + chartHeight - ((val - min) / range) * chartHeight
    return `${x},${y}`
  })

  // Area path: линия графика → вниз за пределы видимости (без горизонтальной линии внизу)
  const firstPoint = points[0]
  const lastPoint = points[points.length - 1]
  const pathD = `M${firstPoint} ${points.slice(1).map(p => `L${p}`).join(' ')} L${lastPoint.split(',')[0]},${height + 2} L0,${height + 2} Z`

  const gradId = `grad-${color.replace(/[^a-zA-Z0-9]/g, '')}-${height}`

  return (
    <svg width={width} height={height} className={styles.sparkline} style={{ overflow: 'hidden' }}>
      <defs>
        <linearGradient id={gradId} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="70%" stopColor={color} stopOpacity="0.06" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d={pathD}
        fill={`url(#${gradId})`}
      />
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}

// Gauge — круговой индикатор процента
function Gauge({ percent, color, size = 64 }: { percent: number; color: string; size?: number }) {
  const radius = (size - 8) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (percent / 100) * circumference

  return (
    <svg width={size} height={size} className={styles.gauge}>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="var(--border-light)"
        strokeWidth="4"
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth="4"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        className={styles.gaugeProgress}
      />
      <text
        x={size / 2}
        y={size / 2}
        textAnchor="middle"
        dominantBaseline="central"
        className={styles.gaugeText}
      >
        {Math.round(percent)}%
      </text>
    </svg>
  )
}

function getStatusColor(percent: number): string {
  if (percent < 60) return 'var(--accent-green, #4CAF50)'
  if (percent < 80) return 'var(--accent-yellow, #FF9800)'
  return 'var(--accent-red, #F44336)'
}

export function ServerMetricsPanel() {
  const [metrics, setMetrics] = useState<ServerMetricsType | null>(null)
  const [history, setHistory] = useState<MetricsHistoryPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [historyHours, setHistoryHours] = useState(6)

  const fetchMetrics = useCallback(async () => {
    try {
      const [currentMetrics, historyData] = await Promise.all([
        api.getServerMetrics(),
        api.getServerMetricsHistory(historyHours),
      ])
      setMetrics(currentMetrics)
      setHistory(historyData.history)
      setError(null)
    } catch (e) {
      setError('Не удалось загрузить метрики сервера')
    } finally {
      setLoading(false)
    }
  }, [historyHours])

  useEffect(() => {
    fetchMetrics()
    // Обновляем каждые 30 секунд
    const interval = setInterval(fetchMetrics, 30000)
    return () => clearInterval(interval)
  }, [fetchMetrics])

  if (loading) {
    return (
      <div className={styles.metricsSection}>
        <div className={styles.sectionHeader}>
          <h3 className={styles.sectionTitle}>Сервер</h3>
        </div>
        <div className={styles.loading}>Загрузка метрик...</div>
      </div>
    )
  }

  if (error || !metrics) {
    return (
      <div className={styles.metricsSection}>
        <div className={styles.sectionHeader}>
          <h3 className={styles.sectionTitle}>Сервер</h3>
        </div>
        <div className={styles.error}>{error || 'Нет данных'}</div>
      </div>
    )
  }

  const cpuHistory = history.map(p => p.cpu)
  const memHistory = history.map(p => p.memory)
  const netRxHistory = history.map(p => p.net_rx)
  const netTxHistory = history.map(p => p.net_tx)

  return (
    <div className={styles.metricsSection}>
      <div className={styles.sectionHeader}>
        <h3 className={styles.sectionTitle}>Сервер</h3>
        <div className={styles.headerRight}>
          <span className={styles.uptime}>Uptime: {metrics.uptime.formatted}</span>
          <div className={styles.historySelector}>
            {[1, 6, 24].map(h => (
              <button
                key={h}
                className={`${styles.histBtn} ${historyHours === h ? styles.histBtnActive : ''}`}
                onClick={() => setHistoryHours(h)}
              >
                {h}ч
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className={styles.metricsGrid}>
        {/* CPU */}
        <div className={styles.metricCard}>
          <div className={styles.metricTop}>
            <Gauge
              percent={metrics.cpu.percent}
              color={getStatusColor(metrics.cpu.percent)}
            />
            <div className={styles.metricInfo}>
              <span className={styles.metricLabel}>CPU</span>
              <span className={styles.metricValue}>{metrics.cpu.percent}%</span>
              <span className={styles.metricSub}>
                {metrics.cpu.cores} ядер | Load: {metrics.cpu.load_1m}
              </span>
            </div>
          </div>
          {cpuHistory.length > 1 && (
            <Sparkline data={cpuHistory} color={getStatusColor(metrics.cpu.percent)} />
          )}
        </div>

        {/* RAM */}
        <div className={styles.metricCard}>
          <div className={styles.metricTop}>
            <Gauge
              percent={metrics.memory.used_percent}
              color={getStatusColor(metrics.memory.used_percent)}
            />
            <div className={styles.metricInfo}>
              <span className={styles.metricLabel}>RAM</span>
              <span className={styles.metricValue}>
                {metrics.memory.used_mb} / {metrics.memory.total_mb} MB
              </span>
              <span className={styles.metricSub}>
                Swap: {metrics.memory.swap_used_mb} / {metrics.memory.swap_total_mb} MB
              </span>
            </div>
          </div>
          {memHistory.length > 1 && (
            <Sparkline data={memHistory} color={getStatusColor(metrics.memory.used_percent)} />
          )}
        </div>

        {/* Disk */}
        <div className={styles.metricCard}>
          <div className={styles.metricTop}>
            <Gauge
              percent={metrics.disk.used_percent}
              color={getStatusColor(metrics.disk.used_percent)}
            />
            <div className={styles.metricInfo}>
              <span className={styles.metricLabel}>Диск</span>
              <span className={styles.metricValue}>
                {metrics.disk.used_gb} / {metrics.disk.total_gb} GB
              </span>
              <span className={styles.metricSub}>
                Свободно: {metrics.disk.available_gb} GB
              </span>
            </div>
          </div>
        </div>

        {/* Network */}
        <div className={styles.metricCard}>
          <div className={styles.metricTop}>
            <div className={styles.netIcon}>
              <svg width="48" height="48" viewBox="0 0 48 48">
                <path d="M14 30 L24 18 L34 30" fill="none" stroke="var(--accent-green, #4CAF50)" strokeWidth="2.5" strokeLinecap="round" />
                <path d="M14 34 L24 46 L34 34" fill="none" stroke="var(--accent-blue, #2196F3)" strokeWidth="2.5" strokeLinecap="round" transform="translate(0,-12)" />
              </svg>
            </div>
            <div className={styles.metricInfo}>
              <span className={styles.metricLabel}>Сеть</span>
              <span className={styles.metricValue}>
                <span className={styles.netUp}>{metrics.network.rx_rate_kbps} KB/s</span>
                {' / '}
                <span className={styles.netDown}>{metrics.network.tx_rate_kbps} KB/s</span>
              </span>
              <span className={styles.metricSub}>
                IN: {metrics.network.rx_total_mb} MB | OUT: {metrics.network.tx_total_mb} MB
              </span>
            </div>
          </div>
          {netRxHistory.length > 1 && (
            <div className={styles.netCharts}>
              <Sparkline data={netRxHistory} color="var(--accent-green, #4CAF50)" height={24} />
              <Sparkline data={netTxHistory} color="var(--accent-blue, #2196F3)" height={24} />
            </div>
          )}
        </div>
      </div>

      {/* Docker контейнеры */}
      {metrics.docker.length > 0 && (
        <div className={styles.dockerSection}>
          <span className={styles.dockerTitle}>Docker</span>
          <div className={styles.dockerList}>
            {metrics.docker.map(c => (
              <div key={c.name} className={styles.dockerItem}>
                <span className={styles.dockerName}>{c.name}</span>
                <span className={styles.dockerStat}>CPU: {c.cpu}</span>
                <span className={styles.dockerStat}>RAM: {c.mem_usage}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
