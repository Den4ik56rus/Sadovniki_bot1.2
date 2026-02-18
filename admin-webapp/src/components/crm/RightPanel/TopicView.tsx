// Topic View - Shows conversation dialog with technical details
import { useState, useEffect, useRef, useMemo } from 'react'
import type { TopicLogsResponse, Message, ConsultationLog, RagSnippet, LlmParams } from '@/types'
import { api } from '@/services/api'
import { useCurrencyStore } from '@/store'
import { CollapsibleSection } from '@/components/common/CollapsibleSection'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './TopicView.module.css'

interface TopicViewProps {
  topicId: number
  onBack: () => void
}

// Helper to parse JSON fields that may come as strings from API
function parseJsonField<T>(value: T | string | null | undefined, fallback: T): T {
  if (value === null || value === undefined) return fallback
  if (typeof value === 'string') {
    try {
      return JSON.parse(value) as T
    } catch {
      return fallback
    }
  }
  return value
}

export function TopicView({ topicId, onBack }: TopicViewProps) {
  const { usdRate } = useCurrencyStore()
  const [data, setData] = useState<TopicLogsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const timelineRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const fetchTopic = async () => {
      try {
        const response = await api.getTopicLogs(topicId)
        setData(response)
      } catch (e) {
        console.error('Failed to fetch topic:', e)
      } finally {
        setIsLoading(false)
      }
    }
    fetchTopic()
  }, [topicId])

  // Scroll to bottom after messages load
  useEffect(() => {
    if (!isLoading && data && timelineRef.current) {
      timelineRef.current.scrollTop = timelineRef.current.scrollHeight
    }
  }, [isLoading, data])

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    try {
      return format(new Date(dateStr), 'd MMM yyyy, HH:mm', { locale: ru })
    } catch {
      return '-'
    }
  }

  const formatTime = (dateStr: string | null) => {
    if (!dateStr) return ''
    try {
      return format(new Date(dateStr), 'HH:mm:ss', { locale: ru })
    } catch {
      return ''
    }
  }

  const formatCost = (costUsd: number) => {
    const costRub = costUsd * usdRate
    if (costRub < 0.01) {
      return `${(costRub * 100).toFixed(2)} коп.`
    }
    if (costRub < 1) {
      return `${(costRub * 100).toFixed(1)} коп.`
    }
    return `${costRub.toFixed(2)} ₽`
  }

  // Parse logs with JSON fields
  const logs = useMemo(() => {
    if (!data?.logs) return []
    return data.logs.map(log => ({
      ...log,
      rag_snippets: parseJsonField<RagSnippet[]>(log.rag_snippets, []),
      llm_params: parseJsonField<LlmParams>(log.llm_params, { model: '', temperature: 0 }),
    }))
  }, [data?.logs])

  // Build timeline: match bot messages with logs
  type TimelineItem =
    | { type: 'message'; data: Message; linkedLog?: ConsultationLog & { rag_snippets: RagSnippet[]; llm_params: LlmParams } }
    | { type: 'log'; data: ConsultationLog & { rag_snippets: RagSnippet[]; llm_params: LlmParams } }

  const timeline = useMemo(() => {
    if (!data?.messages) return []

    // Create Map: bot_response -> log (for fast lookup)
    const logByBotResponse = new Map<string, typeof logs[0]>()
    const usedLogIds = new Set<number>()

    for (const log of logs) {
      const key = log.bot_response?.substring(0, 100) || ''
      if (key && !logByBotResponse.has(key)) {
        logByBotResponse.set(key, log)
      }
    }

    const result: TimelineItem[] = []

    // Sort messages by time
    const sortedMessages = [...data.messages].sort((a, b) => {
      const timeA = a.created_at ? new Date(a.created_at).getTime() : 0
      const timeB = b.created_at ? new Date(b.created_at).getTime() : 0
      return timeA - timeB
    })

    for (const msg of sortedMessages) {
      if (msg.direction === 'bot') {
        // Find LLM log for this bot response
        const key = msg.text?.substring(0, 100) || ''
        const matchingLog = logByBotResponse.get(key)

        if (matchingLog && !usedLogIds.has(matchingLog.id)) {
          // Insert RAG call BEFORE bot response
          result.push({ type: 'log', data: matchingLog })
          usedLogIds.add(matchingLog.id)
          // Bot message with link to log for showing LLM cost
          result.push({ type: 'message', data: msg, linkedLog: matchingLog })
        } else {
          result.push({ type: 'message', data: msg })
        }
      } else {
        result.push({ type: 'message', data: msg })
      }
    }

    // Add remaining logs that weren't matched (at the end)
    for (const log of logs) {
      if (!usedLogIds.has(log.id)) {
        result.push({ type: 'log', data: log })
      }
    }

    return result
  }, [data?.messages, logs])

  // Calculate total cost
  const costSummary = useMemo(() => {
    let totalClassification = 0
    let totalCompose = 0
    let totalEmbedding = 0
    let totalLlm = 0
    let totalCost = 0
    let totalComplexity = 0

    for (const log of logs) {
      totalClassification += log.classification_cost_usd || 0
      totalCompose += log.compose_cost_usd || 0
      totalEmbedding += log.embedding_cost_usd || 0
      totalLlm += log.llm_cost_usd || 0
      totalCost += log.cost_usd || 0
      totalComplexity += log.complexity_classification_cost_usd || 0
    }

    return {
      classification: totalClassification,
      compose: totalCompose,
      embedding: totalEmbedding,
      llm: totalLlm,
      complexity: totalComplexity,
      total: totalCost,
      count: logs.length,
    }
  }, [logs])

  if (isLoading) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <button className={styles.backBtn} onClick={onBack}>
            ← Назад к ленте
          </button>
        </div>
        <div className={styles.loading}>Загрузка...</div>
      </div>
    )
  }

  if (!data || !data.topic) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <button className={styles.backBtn} onClick={onBack}>
            ← Назад к ленте
          </button>
        </div>
        <div className={styles.empty}>Топик не найден</div>
      </div>
    )
  }

  const { topic, messages } = data
  const totalCost = logs.reduce((sum, log) => sum + log.cost_usd, 0)
  // Get category from first log if available
  const category = logs[0]?.consultation_category || 'Консультация'

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <button className={styles.backBtn} onClick={onBack}>
          ← Назад к ленте
        </button>
        <div className={styles.topicInfo}>
          <span className={styles.topicCategory}>
            {category}
          </span>
          {topic.culture && (
            <span className={styles.topicCulture}>{topic.culture}</span>
          )}
          <span className={`${styles.topicStatus} ${styles[topic.status]}`}>
            {topic.status === 'open' ? 'Активен' : 'Закрыт'}
          </span>
        </div>
      </div>

      {/* Topic stats */}
      <div className={styles.stats}>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Начало</span>
          <span className={styles.statValue}>{formatDate(topic.created_at)}</span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Сообщений</span>
          <span className={styles.statValue}>{messages.length}</span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Расходы</span>
          <span className={styles.statValue}>{formatCost(totalCost)}</span>
        </div>
      </div>

      {/* Timeline with technical details */}
      <div className={styles.timeline} ref={timelineRef}>
        {timeline.map((item) => {
          if (item.type === 'message') {
            const msg = item.data
            const linkedLog = 'linkedLog' in item ? item.linkedLog : undefined
            return (
              <div
                key={`msg-${msg.id}`}
                className={`${styles.timelineItem} ${msg.direction === 'user' ? styles.timelineUser : styles.timelineBot}`}
              >
                <div className={styles.timelineLabel}>
                  {msg.direction === 'user' ? '👤 Пользователь' : '🤖 Бот'}
                  {msg.meta?.type === 'callback' && (
                    <span className={styles.badgeCallback}>кнопка</span>
                  )}
                  {msg.created_at && (
                    <span className={styles.timelineTime}>
                      {formatTime(msg.created_at)}
                    </span>
                  )}
                </div>
                <div className={styles.timelineText}>{msg.text}</div>

                {/* Inline keyboard buttons */}
                {msg.meta?.keyboard?.buttons && (
                  <div className={styles.keyboardButtons}>
                    {(msg.meta.keyboard.buttons as Array<Array<{text: string; callback_data?: string}>>).map((row, ri) => (
                      <div key={ri} className={styles.keyboardRow}>
                        {row.map((btn, bi) => (
                          <span key={bi} className={styles.keyboardBtn}>
                            {btn.text}
                          </span>
                        ))}
                      </div>
                    ))}
                  </div>
                )}

                {/* LLM cost and technical details - only for bot responses */}
                {msg.direction === 'bot' && linkedLog && (
                  <>
                    <div className={styles.llmCostInline}>
                      <span className={styles.llmCostTokens}>
                        {(linkedLog.prompt_tokens || 0).toLocaleString()} → {(linkedLog.completion_tokens || 0).toLocaleString()} tok
                      </span>
                      <span className={styles.llmCostValue}>
                        💰 {formatCost(linkedLog.llm_cost_usd || 0)}
                      </span>
                      <span className={styles.llmCostModel}>{linkedLog.llm_params?.model || 'gpt-4o'}</span>
                      <span className={styles.llmCostLatency}>{linkedLog.latency_ms || 0}ms</span>
                    </div>

                    {/* RAG Snippets for this response */}
                    {linkedLog.rag_snippets && linkedLog.rag_snippets.length > 0 && (
                      <div className={styles.technicalDataInline}>
                        <CollapsibleSection
                          title="RAG Сниппеты"
                          badge={`${linkedLog.rag_snippets.length}`}
                          defaultOpen={false}
                        >
                          <div className={styles.snippets}>
                            {linkedLog.rag_snippets.map((snippet, idx) => (
                              <div key={idx} className={styles.snippet}>
                                <div className={styles.snippetHeader}>
                                  <span
                                    className={`${styles.badge} ${snippet.source_type === 'qa' ? styles.badgeInfo : styles.badgeWarning}`}
                                  >
                                    {snippet.source_type === 'qa' ? 'Q&A' : 'Doc'}
                                  </span>
                                  <span className={styles.snippetMeta}>
                                    L{snippet.priority_level} | {snippet.distance.toFixed(3)}
                                  </span>
                                </div>
                                <pre className={styles.snippetContent}>{snippet.content}</pre>
                              </div>
                            ))}
                          </div>
                        </CollapsibleSection>
                      </div>
                    )}

                    {/* System prompt for this response */}
                    {linkedLog.system_prompt && (
                      <div className={styles.technicalDataInline}>
                        <CollapsibleSection
                          title="Системный промпт"
                          badge={`${linkedLog.system_prompt.length}`}
                          defaultOpen={false}
                        >
                          <pre className={styles.codeBlock}>{linkedLog.system_prompt}</pre>
                        </CollapsibleSection>
                      </div>
                    )}
                  </>
                )}
              </div>
            )
          } else {
            const log = item.data
            const ragCost = (log.compose_cost_usd || 0) + (log.embedding_cost_usd || 0)
            const ragTokens = (log.compose_tokens || 0) + (log.embedding_tokens || 0)
            const hasClassification = (log.classification_cost_usd || 0) > 0
            const hasComplexity = !!(log.complexity_tier)
            const complexityMeta = parseJsonField<Record<string, unknown>>(log.complexity_metadata, {})
            const tierLabels: Record<string, string> = {
              short_answer: 'Краткий ответ',
              long_answer: 'План на фазу',
              turnkey_solution: 'Готовое решение',
            }
            const tierCostLabels: Record<string, string> = {
              short_answer: '1 вопрос',
              long_answer: '2 вопроса',
              turnkey_solution: 'покупка',
            }
            return (
              <div key={`log-${log.id}`}>
                {/* Classification block - show first if exists */}
                {hasClassification && (
                  <div className={`${styles.timelineItem} ${styles.timelineClassification}`}>
                    <div className={styles.timelineLabel}>
                      🏷️ Классификация
                      {log.created_at && (
                        <span className={styles.timelineTime}>
                          {formatTime(log.created_at)}
                        </span>
                      )}
                    </div>
                    <div className={styles.classificationInfo}>
                      {log.consultation_category && (
                        <span className={styles.classificationCategory}>
                          категория: {log.consultation_category}
                        </span>
                      )}
                      {log.culture && (
                        <span className={styles.classificationCulture}>
                          культура: {log.culture}
                        </span>
                      )}
                    </div>
                    <div className={styles.classificationCostInline}>
                      <span className={styles.classificationCostTokens}>
                        {(log.classification_tokens || 0).toLocaleString()} tok
                      </span>
                      <span className={styles.classificationCostValue}>
                        💰 {formatCost(log.classification_cost_usd || 0)}
                      </span>
                    </div>
                  </div>
                )}

                {/* Complexity classification block */}
                {hasComplexity && (
                  <div className={`${styles.timelineItem} ${styles.timelineComplexity}`}>
                    <div className={styles.timelineLabel}>
                      ⚖️ Сложность
                      {log.created_at && (
                        <span className={styles.timelineTime}>
                          {formatTime(log.created_at)}
                        </span>
                      )}
                    </div>
                    <div className={styles.complexityInfo}>
                      <span className={`${styles.complexityTier} ${styles[`tier_${log.complexity_tier}`] || ''}`}>
                        {tierLabels[log.complexity_tier || ''] || log.complexity_tier}
                      </span>
                      <span className={styles.complexityPrice}>
                        {tierCostLabels[log.complexity_tier || ''] || ''}
                      </span>
                      {complexityMeta.current_phase && (
                        <span className={styles.complexityPhase}>
                          фаза: {String(complexityMeta.current_phase)}
                        </span>
                      )}
                      {complexityMeta.topics && Array.isArray(complexityMeta.topics) && (complexityMeta.topics as string[]).length > 0 && (
                        <span className={styles.complexityTopics}>
                          темы: {(complexityMeta.topics as string[]).join(', ')}
                        </span>
                      )}
                    </div>
                    {(log.complexity_classification_cost_usd || 0) > 0 && (
                      <div className={styles.complexityCostInline}>
                        <span className={styles.complexityCostTokens}>
                          {(log.complexity_classification_tokens || 0).toLocaleString()} tok
                        </span>
                        <span className={styles.complexityCostValue}>
                          💰 {formatCost(log.complexity_classification_cost_usd || 0)}
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {/* RAG search block */}
                <div className={`${styles.timelineItem} ${styles.timelineLlm}`}>
                  <div className={styles.timelineLabel}>
                    🔍 RAG поиск
                    {log.created_at && (
                      <span className={styles.timelineTime}>
                        {formatTime(log.created_at)}
                      </span>
                    )}
                  </div>

                  {/* RAG Query */}
                  {log.composed_question && (
                    <div className={styles.ragQueryInline}>
                      {log.composed_question}
                    </div>
                  )}

                  {/* RAG cost (compose + embedding) */}
                  {ragTokens > 0 && (
                    <div className={styles.ragCostInline}>
                      <span className={styles.ragCostTokens}>
                        {(log.compose_tokens || 0).toLocaleString()} + {(log.embedding_tokens || 0).toLocaleString()} tok
                      </span>
                      <span className={styles.ragCostValue}>
                        💰 {formatCost(ragCost)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )
          }
        })}
      </div>

      {/* Total cost summary */}
      {logs.length > 0 && (
        <div className={styles.totalCostSummary}>
          <div className={styles.totalCostFinal}>
            <span className={styles.totalCostFinalLabel}>💵 ИТОГО ЗА КОНСУЛЬТАЦИЮ:</span>
            <span className={styles.totalCostFinalValue}>{formatCost(costSummary.total)}</span>
          </div>
          <div className={styles.totalCostUsd}>
            (${costSummary.total.toFixed(6)} за {costSummary.count} LLM вызов{costSummary.count === 1 ? '' : costSummary.count < 5 ? 'а' : 'ов'})
          </div>
        </div>
      )}
    </div>
  )
}
