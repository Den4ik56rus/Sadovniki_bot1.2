// Article View - Shows article details with RAG snippets and prompts
import { useState, useEffect, useMemo } from 'react'
import type { AdminArticle, RagSnippet } from '@/types'
import { api } from '@/services/api'
import { useCurrencyStore } from '@/store'
import { CollapsibleSection } from '@/components/common/CollapsibleSection'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './ArticleView.module.css'

interface ArticleViewProps {
  articleId: number
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

export function ArticleView({ articleId, onBack }: ArticleViewProps) {
  const { usdRate } = useCurrencyStore()
  const [article, setArticle] = useState<AdminArticle | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchArticle = async () => {
      try {
        const response = await api.getArticle(articleId)
        setArticle(response)
      } catch (e) {
        console.error('Failed to fetch article:', e)
      } finally {
        setIsLoading(false)
      }
    }
    fetchArticle()
  }, [articleId])

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    try {
      return format(new Date(dateStr), 'd MMM yyyy, HH:mm', { locale: ru })
    } catch {
      return '-'
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

  // Parse RAG snippets
  const ragSnippets = useMemo(() => {
    if (!article?.rag_snippets) return []
    return parseJsonField<RagSnippet[]>(article.rag_snippets, [])
  }, [article?.rag_snippets])

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

  if (!article) {
    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <button className={styles.backBtn} onClick={onBack}>
            ← Назад к ленте
          </button>
        </div>
        <div className={styles.empty}>Статья не найдена</div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <button className={styles.backBtn} onClick={onBack}>
          ← Назад к ленте
        </button>
        <div className={styles.articleInfo}>
          <span className={styles.articleLabel}>📄 Статья</span>
          <span className={styles.articleId}>ID: {article.id}</span>
        </div>
      </div>

      {/* Topic */}
      <div className={styles.topic}>
        <h2 className={styles.topicTitle}>{article.topic}</h2>
        <div className={styles.topicMeta}>
          <span>{formatDate(article.created_at)}</span>
          <span>•</span>
          <span>{article.article_text.length.toLocaleString()} символов</span>
        </div>
      </div>

      {/* Stats */}
      <div className={styles.stats}>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Модель</span>
          <span className={styles.statValue}>{article.llm_model || 'gpt-4o'}</span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>RAG сниппетов</span>
          <span className={styles.statValue}>{article.rag_snippets_count}</span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Стоимость</span>
          <span className={styles.statValue}>{formatCost(article.cost_usd)}</span>
        </div>
      </div>

      {/* Token breakdown */}
      <div className={styles.tokenBreakdown}>
        <div className={styles.tokenRow}>
          <span className={styles.tokenLabel}>Embedding</span>
          <span className={styles.tokenValue}>{article.embedding_tokens.toLocaleString()} tok</span>
        </div>
        <div className={styles.tokenRow}>
          <span className={styles.tokenLabel}>LLM Prompt</span>
          <span className={styles.tokenValue}>{article.llm_prompt_tokens.toLocaleString()} tok</span>
        </div>
        <div className={styles.tokenRow}>
          <span className={styles.tokenLabel}>LLM Completion</span>
          <span className={styles.tokenValue}>{article.llm_completion_tokens.toLocaleString()} tok</span>
        </div>
        <div className={`${styles.tokenRow} ${styles.tokenTotal}`}>
          <span className={styles.tokenLabel}>Всего</span>
          <span className={styles.tokenValue}>{article.total_tokens.toLocaleString()} tok</span>
        </div>
      </div>

      {/* Article text */}
      <div className={styles.content}>
        <CollapsibleSection
          title="Текст статьи"
          badge={`${article.article_text.length.toLocaleString()} символов`}
          defaultOpen={true}
        >
          <div className={styles.articleText}>
            {article.article_text}
          </div>
        </CollapsibleSection>
      </div>

      {/* RAG Snippets */}
      {ragSnippets.length > 0 && (
        <div className={styles.section}>
          <CollapsibleSection
            title="RAG Сниппеты"
            badge={`${ragSnippets.length}`}
            defaultOpen={false}
          >
            <div className={styles.snippets}>
              {ragSnippets.map((snippet, idx) => (
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
                    {snippet.category && (
                      <span className={styles.snippetCategory}>{snippet.category}</span>
                    )}
                  </div>
                  <pre className={styles.snippetContent}>{snippet.content}</pre>
                </div>
              ))}
            </div>
          </CollapsibleSection>
        </div>
      )}

      {/* System prompt */}
      {article.system_prompt && (
        <div className={styles.section}>
          <CollapsibleSection
            title="Системный промпт"
            badge={`${article.system_prompt.length.toLocaleString()}`}
            defaultOpen={false}
          >
            <pre className={styles.codeBlock}>{article.system_prompt}</pre>
          </CollapsibleSection>
        </div>
      )}

      {/* Cost summary */}
      <div className={styles.totalCostSummary}>
        <div className={styles.totalCostFinal}>
          <span className={styles.totalCostFinalLabel}>💵 СТОИМОСТЬ СТАТЬИ:</span>
          <span className={styles.totalCostFinalValue}>{formatCost(article.cost_usd)}</span>
        </div>
        <div className={styles.totalCostUsd}>
          (${article.cost_usd.toFixed(6)})
        </div>
        <div className={styles.adminNote}>
          Токены НЕ списаны с баланса (админский режим)
        </div>
      </div>
    </div>
  )
}
