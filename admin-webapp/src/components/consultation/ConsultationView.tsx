import { useEffect, useMemo, useCallback } from 'react'
import { useLogsStore, useUIStore, useCurrencyStore } from '@/store'
import { useSSE } from '@/hooks/useSSE'
import { useScrollPreservation } from '@/hooks/useScrollPreservation'
import { api } from '@/services/api'
import { CollapsibleSection } from '@/components/common/CollapsibleSection'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './ConsultationView.module.css'

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

export function ConsultationView() {
  const {
    logs: rawLogs,
    messages,
    topicInfo,
    isLoading,
    error,
    fetchLogs,
    clearLogs,
    addLog,
    addMessage,
    setSseConnected,
  } = useLogsStore()
  const { selectedTopicId } = useUIStore()
  const { usdRate, fetchRate } = useCurrencyStore()

  const { containerRef, handleScroll } = useScrollPreservation({
    enabled: true,
    autoScrollThreshold: 100,
  })

  // Parse JSON fields in logs
  const logs = useMemo(() => {
    return rawLogs.map(log => ({
      ...log,
      rag_snippets: parseJsonField(log.rag_snippets, []),
      llm_params: parseJsonField(log.llm_params, { model: '', temperature: 0 }),
    }))
  }, [rawLogs])

  // Строим timeline: для каждого bot message находим соответствующий LLM log
  // RAG вызов показывается ПЕРЕД ответом бота, а стоимость LLM — В ответе бота
  type TimelineItem =
    | { type: 'message'; data: typeof messages[0]; linkedLog?: typeof logs[0] }
    | { type: 'log'; data: typeof logs[0] }

  const timeline = useMemo(() => {
    // Создаём Map: bot_response -> log (для быстрого поиска)
    const logByBotResponse = new Map<string, typeof logs[0]>()
    const usedLogIds = new Set<number>()

    for (const log of logs) {
      // Сохраняем по первым 100 символам bot_response для matching
      const key = log.bot_response?.substring(0, 100) || ''
      if (key && !logByBotResponse.has(key)) {
        logByBotResponse.set(key, log)
      }
    }

    const result: TimelineItem[] = []

    // Сортируем сообщения по времени
    const sortedMessages = [...messages].sort((a, b) => {
      const timeA = a.created_at ? new Date(a.created_at).getTime() : 0
      const timeB = b.created_at ? new Date(b.created_at).getTime() : 0
      return timeA - timeB
    })

    for (const msg of sortedMessages) {
      if (msg.direction === 'bot') {
        // Ищем LLM log для этого ответа бота
        const key = msg.text?.substring(0, 100) || ''
        const matchingLog = logByBotResponse.get(key)

        if (matchingLog && !usedLogIds.has(matchingLog.id)) {
          // Вставляем RAG вызов ПЕРЕД ответом бота
          result.push({ type: 'log', data: matchingLog })
          usedLogIds.add(matchingLog.id)
          // Bot message со ссылкой на log для показа стоимости LLM
          result.push({ type: 'message', data: msg, linkedLog: matchingLog })
        } else {
          result.push({ type: 'message', data: msg })
        }
      } else {
        result.push({ type: 'message', data: msg })
      }
    }

    // Добавляем оставшиеся logs которые не были matched (в конец)
    for (const log of logs) {
      if (!usedLogIds.has(log.id)) {
        result.push({ type: 'log', data: log })
      }
    }

    return result
  }, [messages, logs])

  useEffect(() => {
    if (selectedTopicId) {
      fetchLogs(selectedTopicId)
      fetchRate()
    } else {
      clearLogs()
    }
  }, [selectedTopicId, fetchLogs, clearLogs, fetchRate])

  // SSE connection for topic logs
  const handleSSEMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)

        // Игнорируем heartbeat
        if (event.type === 'heartbeat') return

        // Обрабатываем new_log события
        if (event.type === 'new_log') {
          console.log('[ConsultationView] Received new_log event:', {
            id: data.id,
            user_message: data.user_message?.substring(0, 50),
            llm_cost_usd: data.llm_cost_usd,
            composed_question: data.composed_question?.substring(0, 50),
            rag_snippets_count: data.rag_snippets?.length,
          })

          // Добавляем дефолтные значения для полей, которых может не быть в SSE
          const normalizedLog = {
            ...data,
            rag_snippets: data.rag_snippets || [],
            llm_params: data.llm_params || { model: 'gpt-4o', temperature: 0 },
            system_prompt: data.system_prompt || '',
            composed_question: data.composed_question || '',
            compose_tokens: data.compose_tokens || 0,
            compose_cost_usd: data.compose_cost_usd || 0,
            embedding_tokens: data.embedding_tokens || 0,
            embedding_cost_usd: data.embedding_cost_usd || 0,
            classification_tokens: data.classification_tokens || 0,
            classification_cost_usd: data.classification_cost_usd || 0,
            llm_cost_usd: data.llm_cost_usd || 0,
          }

          console.log('[ConsultationView] Adding normalized log to store')
          addLog(normalizedLog)
        }

        // Обрабатываем new_message события
        if (event.type === 'new_message') {
          addMessage(data)
        }
      } catch (error) {
        console.error('[ConsultationView] Failed to parse SSE event:', error, event)
      }
    },
    [addLog, addMessage]
  )

  const { isConnected, error: sseError } = useSSE({
    endpoint: selectedTopicId ? api.sse.topicLogs(selectedTopicId) : '',
    onMessage: handleSSEMessage,
    enabled: !!selectedTopicId,
  })

  useEffect(() => {
    setSseConnected(isConnected)
  }, [isConnected, setSseConnected])

  // Convert USD to RUB with smart formatting
  const toRub = (usd: number) => {
    const rub = usd * usdRate
    if (rub < 0.01) {
      return `${(rub * 100).toFixed(2)} коп.`
    }
    if (rub < 1) {
      return `${(rub * 100).toFixed(1)} коп.`
    }
    return `${rub.toFixed(2)} ₽`
  }

  // Считаем общую стоимость топика и разбивку по типам
  const costSummary = useMemo(() => {
    let totalClassification = 0
    let totalCompose = 0
    let totalEmbedding = 0
    let totalLlm = 0
    let totalCost = 0

    for (const log of logs) {
      totalClassification += log.classification_cost_usd || 0
      totalCompose += log.compose_cost_usd || 0
      totalEmbedding += log.embedding_cost_usd || 0
      totalLlm += log.llm_cost_usd || 0
      totalCost += log.cost_usd || 0
    }

    return {
      classification: totalClassification,
      compose: totalCompose,
      embedding: totalEmbedding,
      llm: totalLlm,
      total: totalCost,
      count: logs.length,
    }
  }, [logs])

  if (!selectedTopicId) {
    return (
      <div className={styles.empty}>
        Выберите топик для просмотра консультации
      </div>
    )
  }

  if (isLoading) {
    return <div className={styles.loading}>Загрузка...</div>
  }

  if (error) {
    return <div className={styles.error}>Ошибка: {error}</div>
  }

  if (timeline.length === 0) {
    return <div className={styles.empty}>Нет данных для этого топика</div>
  }

  return (
    <div className={styles.container}>
      {topicInfo && (
        <div className={styles.header}>
          <h3>
            Консультация #{topicInfo.id}
            {topicInfo.culture && (
              <span className={styles.culture}>{topicInfo.culture}</span>
            )}
          </h3>
          <div className={styles.userInfo}>
            {topicInfo.user.first_name || topicInfo.user.username || `User #${topicInfo.user.telegram_user_id}`}
          </div>

          {/* SSE Connection Indicator */}
          <div className={styles.sseStatus}>
            <span
              className={`${styles.indicator} ${
                isConnected ? styles.connected : styles.disconnected
              }`}
              title={isConnected ? 'Подключено к SSE' : 'Отключено от SSE'}
            >
              {isConnected ? '🟢 Live' : '🔴 Offline'}
            </span>
            {sseError && (
              <span className={styles.errorText} title={sseError}>
                {sseError}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Единый timeline */}
      <div className={styles.timeline} ref={containerRef} onScroll={handleScroll}>
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
                  {msg.created_at && (
                    <span className={styles.timelineTime}>
                      {format(new Date(msg.created_at), 'HH:mm:ss', { locale: ru })}
                    </span>
                  )}
                </div>
                <div className={styles.timelineText}>{msg.text}</div>
                {/* Стоимость LLM консультации — только для ответов бота */}
                {msg.direction === 'bot' && linkedLog && (
                  <>
                    <div className={styles.llmCostInline}>
                      <span className={styles.llmCostTokens}>
                        {(linkedLog.prompt_tokens || 0).toLocaleString()} → {(linkedLog.completion_tokens || 0).toLocaleString()} tok
                      </span>
                      <span className={styles.llmCostValue}>
                        💰 {toRub(linkedLog.llm_cost_usd || 0)}
                      </span>
                      <span className={styles.llmCostModel}>{linkedLog.llm_params?.model || 'gpt-4o'}</span>
                      <span className={styles.llmCostLatency}>{linkedLog.latency_ms || 0}ms</span>
                    </div>

                    {/* RAG Сниппеты для этого ответа */}
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
                                    className={`badge ${snippet.source_type === 'qa' ? 'badge-info' : 'badge-warning'}`}
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

                    {/* Системный промпт для этого ответа */}
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
            return (
              <div key={`log-${log.id}`}>
                {/* Блок классификации — показываем первым, если есть */}
                {hasClassification && (
                  <div className={`${styles.timelineItem} ${styles.timelineClassification}`}>
                    <div className={styles.timelineLabel}>
                      🏷️ Классификация
                      {log.created_at && (
                        <span className={styles.timelineTime}>
                          {format(new Date(log.created_at), 'HH:mm:ss', { locale: ru })}
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
                        💰 {toRub(log.classification_cost_usd || 0)}
                      </span>
                    </div>
                  </div>
                )}

                {/* Блок RAG поиска */}
                <div className={`${styles.timelineItem} ${styles.timelineLlm}`}>
                  <div className={styles.timelineLabel}>
                    🔍 RAG поиск
                    {log.created_at && (
                      <span className={styles.timelineTime}>
                        {format(new Date(log.created_at), 'HH:mm:ss', { locale: ru })}
                      </span>
                    )}
                  </div>

                  {/* RAG Query */}
                  {log.composed_question && (
                    <div className={styles.ragQueryInline}>
                      {log.composed_question}
                    </div>
                  )}

                  {/* Стоимость RAG (compose + embedding) */}
                  {ragTokens > 0 && (
                    <div className={styles.ragCostInline}>
                      <span className={styles.ragCostTokens}>
                        {(log.compose_tokens || 0).toLocaleString()} + {(log.embedding_tokens || 0).toLocaleString()} tok
                      </span>
                      <span className={styles.ragCostValue}>
                        💰 {toRub(ragCost)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )
          }
        })}
      </div>

      {/* Итого за консультацию */}
      {logs.length > 0 && (
        <div className={styles.totalCostSummary}>
          <div className={styles.totalCostFinal}>
            <span className={styles.totalCostFinalLabel}>💵 ИТОГО ЗА КОНСУЛЬТАЦИЮ:</span>
            <span className={styles.totalCostFinalValue}>{toRub(costSummary.total)}</span>
          </div>
          <div className={styles.totalCostUsd}>
            (${costSummary.total.toFixed(6)} за {costSummary.count} LLM вызов{costSummary.count === 1 ? '' : costSummary.count < 5 ? 'а' : 'ов'})
          </div>
        </div>
      )}
    </div>
  )
}
