// GuidesPage — управление PDF-гайдами (Готовые решения)

import { Fragment, useEffect, useState } from 'react'
import { useGuidesStore } from '@/store/guidesStore'
import type { GuideOrder, GuideSectionMeta } from '@/types'
import styles from './GuidesPage.module.css'

const STATUS_LABELS: Record<string, string> = {
  pending: 'Ожидание',
  payment_pending: 'Оплата',
  generating: 'Генерация',
  completed: 'Завершено',
  failed: 'Ошибка',
}

const STATUS_FILTERS = [
  { value: undefined, label: 'Все' },
  { value: 'completed', label: 'Завершено' },
  { value: 'generating', label: 'Генерация' },
  { value: 'failed', label: 'Ошибка' },
]

// Порядок секций для отображения
const SECTION_ORDER = [
  'intro',
  'nutrition',
  'protection',
  'soil_prep',
  'care_works',
]

function getStatusClass(status: string): string {
  switch (status) {
    case 'completed': return styles.statusCompleted
    case 'generating': return styles.statusGenerating
    case 'failed': return styles.statusFailed
    default: return styles.statusPending
  }
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })
  } catch {
    return dateStr
  }
}

function formatCost(cost: number): string {
  return `$${cost.toFixed(4)}`
}

function formatTokens(tokens: number): string {
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}k`
  return String(tokens)
}

function getUserName(order: GuideOrder): string {
  if (order.username) return `@${order.username}`
  if (order.first_name) return order.first_name
  return `#${order.user_id}`
}

// ── Section Detail (expandable per-section cost table) ────────────────────

function SectionDetail({ order }: { order: GuideOrder }) {
  const [showQuestion, setShowQuestion] = useState<string | null>(null)
  const [showSystem, setShowSystem] = useState<string | null>(null)
  const meta = order.sections_meta

  if (!meta) {
    return <span className={styles.noDetail}>Детализация недоступна (старый заказ)</span>
  }

  const sortedKeys = SECTION_ORDER.filter((k) => k in meta)
  // Add any keys not in SECTION_ORDER
  Object.keys(meta).forEach((k) => {
    if (!sortedKeys.includes(k)) sortedKeys.push(k)
  })

  let totalPrompt = 0
  let totalCompletion = 0
  let totalCost = 0

  sortedKeys.forEach((k) => {
    const s = meta[k]
    totalPrompt += s.prompt_tokens
    totalCompletion += s.completion_tokens
    totalCost += s.cost_usd
  })

  return (
    <div>
      <div className={styles.detailTitle}>Посекционные затраты</div>
      <table className={styles.sectionsTable}>
        <thead>
          <tr>
            <th>Секция</th>
            <th>Промпт</th>
            <th>Ответ</th>
            <th>Стоимость</th>
            <th>Модель</th>
            <th>RAG</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {sortedKeys.map((key) => {
            const s: GuideSectionMeta = meta[key]
            return (
              <Fragment key={key}>
                <tr>
                  <td>{s.title}</td>
                  <td className={styles.tokenValue}>{formatTokens(s.prompt_tokens)}</td>
                  <td className={styles.tokenValue}>{formatTokens(s.completion_tokens)}</td>
                  <td className={styles.costValue}>{formatCost(s.cost_usd)}</td>
                  <td><span className={styles.modelBadge}>{s.model || '—'}</span></td>
                  <td className={styles.tokenValue}>{s.rag_snippets_count}</td>
                  <td className={styles.promptButtons}>
                    <button
                      className={styles.questionToggle}
                      onClick={(e) => { e.stopPropagation(); setShowQuestion(showQuestion === key ? null : key); setShowSystem(null) }}
                    >
                      {showQuestion === key ? 'Скрыть' : 'Вопрос'}
                    </button>
                    {s.system_prompt && (
                      <button
                        className={styles.systemToggle}
                        onClick={(e) => { e.stopPropagation(); setShowSystem(showSystem === key ? null : key); setShowQuestion(null) }}
                      >
                        {showSystem === key ? 'Скрыть' : 'Системный'}
                      </button>
                    )}
                  </td>
                </tr>
                {showQuestion === key && (
                  <tr>
                    <td colSpan={7} style={{ padding: '0 12px 12px' }}>
                      <div className={styles.promptLabel}>Вопрос пользователя</div>
                      <div className={styles.questionText}>{s.user_question}</div>
                    </td>
                  </tr>
                )}
                {showSystem === key && (
                  <tr>
                    <td colSpan={7} style={{ padding: '0 12px 12px' }}>
                      <div className={styles.promptLabel}>Системный промпт</div>
                      <pre className={styles.systemPromptText}>{s.system_prompt}</pre>
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
          <tr className={styles.totalRow}>
            <td>Итого</td>
            <td className={styles.tokenValue}>{formatTokens(totalPrompt)}</td>
            <td className={styles.tokenValue}>{formatTokens(totalCompletion)}</td>
            <td className={styles.costValue}>{formatCost(totalCost)}</td>
            <td></td>
            <td></td>
            <td></td>
          </tr>
        </tbody>
      </table>

      {order.error_message && (
        <div className={styles.errorMessage}>
          Ошибка: {order.error_message}
        </div>
      )}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────

export function GuidesPage() {
  const {
    orders,
    stats,
    expandedId,
    isLoading,
    error,
    statusFilter,
    fetchOrders,
    fetchStats,
    setStatusFilter,
    toggleExpanded,
  } = useGuidesStore()

  useEffect(() => {
    fetchOrders()
    fetchStats()
  }, [fetchOrders, fetchStats])

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h2>Готовые решения</h2>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className={styles.summaryCards}>
          <div className={styles.summaryCard}>
            <div className={styles.summaryValue}>{stats.total_orders}</div>
            <div className={styles.summaryLabel}>Всего заказов</div>
          </div>
          <div className={styles.summaryCard}>
            <div className={styles.summaryValue}>{stats.completed_orders}</div>
            <div className={styles.summaryLabel}>Завершено</div>
          </div>
          <div className={styles.summaryCard}>
            <div className={styles.summaryValue}>{formatCost(stats.total_cost_usd)}</div>
            <div className={styles.summaryLabel}>Общая стоимость LLM</div>
          </div>
          <div className={styles.summaryCard}>
            <div className={styles.summaryValue}>{formatCost(stats.avg_cost_usd)}</div>
            <div className={styles.summaryLabel}>Средняя стоимость</div>
          </div>
        </div>
      )}

      {/* Status Filter */}
      <div className={styles.statusFilter}>
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.label}
            className={`${styles.filterButton} ${statusFilter === f.value ? styles.filterActive : ''}`}
            onClick={() => setStatusFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className={styles.loading}>Загрузка...</div>
      ) : error ? (
        <div className={styles.error}>Ошибка: {error}</div>
      ) : orders.length === 0 ? (
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>📖</div>
          <div className={styles.emptyText}>Нет заказов на гайды</div>
          <div className={styles.emptyHint}>Заказы появятся после покупки «Готового решения» пользователями</div>
        </div>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th></th>
              <th>ID</th>
              <th>Культура</th>
              <th>Пользователь</th>
              <th>Статус</th>
              <th>Модель</th>
              <th>Стоимость</th>
              <th>Токены</th>
              <th>Дата</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => {
              const isExpanded = expandedId === order.id
              return (
                <Fragment key={order.id}>
                  <tr
                    className={`${styles.clickableRow} ${isExpanded ? styles.expandedRow : ''}`}
                    onClick={() => toggleExpanded(order.id)}
                  >
                    <td>
                      <span className={`${styles.expandArrow} ${isExpanded ? styles.expandArrowOpen : ''}`}>
                        &#x25B6;
                      </span>
                    </td>
                    <td>{order.id}</td>
                    <td className={styles.cultureDisplay}>{order.culture_display}</td>
                    <td className={styles.username}>{getUserName(order)}</td>
                    <td>
                      <span className={`${styles.statusBadge} ${getStatusClass(order.status)}`}>
                        {STATUS_LABELS[order.status] || order.status}
                      </span>
                    </td>
                    <td>
                      {order.llm_model
                        ? <span className={styles.modelBadge}>{order.llm_model}</span>
                        : <span className={styles.tokenValue}>—</span>
                      }
                    </td>
                    <td className={styles.costValue}>{formatCost(order.total_llm_cost_usd)}</td>
                    <td className={styles.tokenValue}>{formatTokens(order.total_llm_tokens)}</td>
                    <td className={styles.dateCell}>{formatDate(order.created_at)}</td>
                  </tr>
                  {isExpanded && (
                    <tr>
                      <td colSpan={9} className={styles.detailCell}>
                        <div className={styles.detailContainer}>
                          <SectionDetail order={order} />
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
