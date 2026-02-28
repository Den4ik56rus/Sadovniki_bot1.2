// Articles Page — standalone page for generating and viewing admin articles
import { useState, useEffect, useCallback } from 'react'
import { api } from '@/services/api'
import { ArticleView } from '@/components/crm/RightPanel/ArticleView'
import type { AdminArticleListItem, GenerateArticleDto } from '@/types'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './ArticlesPage.module.css'

type Mode = 'list' | 'detail'

const CATEGORIES = [
  { value: '', label: 'Не указано (вся база)' },
  { value: 'питание растений', label: 'Питание растений' },
  { value: 'посадка и уход', label: 'Посадка и уход' },
  { value: 'защита растений', label: 'Защита растений' },
  { value: 'улучшение почвы', label: 'Улучшение почвы' },
  { value: 'подбор сорта', label: 'Подбор сорта' },
]

const CULTURES = [
  { value: '', label: 'Не указано' },
  { value: 'малина', label: 'Малина' },
  { value: 'клубника', label: 'Клубника' },
  { value: 'голубика', label: 'Голубика' },
  { value: 'смородина', label: 'Смородина' },
  { value: 'крыжовник', label: 'Крыжовник' },
  { value: 'ежевика', label: 'Ежевика' },
]

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  try {
    return format(new Date(dateStr), 'd MMM yyyy, HH:mm', { locale: ru })
  } catch {
    return '—'
  }
}

const LS_KEY = 'articles_form_prefs'

function loadPrefs() {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || '{}')
  } catch { return {} }
}

function savePrefs(patch: Record<string, unknown>) {
  try {
    const current = loadPrefs()
    localStorage.setItem(LS_KEY, JSON.stringify({ ...current, ...patch }))
  } catch { /* ignore */ }
}

export function ArticlesPage() {
  const [mode, setMode] = useState<Mode>('list')
  const [selectedArticleId, setSelectedArticleId] = useState<number | null>(null)

  // Form state — defaults from localStorage
  const prefs = loadPrefs()
  const [topic, setTopic] = useState('')
  const [category, setCategory] = useState<string>(prefs.category ?? '')
  const [culture, setCulture] = useState<string>(prefs.culture ?? '')
  const [modelOverride, setModelOverride] = useState<string>(prefs.modelOverride ?? '')
  const [useScripts, setUseScripts] = useState<boolean>(prefs.useScripts ?? true)
  const [useConsultationPrompt, setUseConsultationPrompt] = useState<boolean>(prefs.useConsultationPrompt ?? false)
  const [useRag, setUseRag] = useState<boolean>(prefs.useRag ?? true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [generateError, setGenerateError] = useState<string | null>(null)

  // Models from settings
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [defaultModel, setDefaultModel] = useState<string>('')

  // Articles list
  const [articles, setArticles] = useState<AdminArticleListItem[]>([])
  const [total, setTotal] = useState(0)
  const [isLoadingList, setIsLoadingList] = useState(false)

  // Load models on mount
  useEffect(() => {
    api.getLlmConfig()
      .then(config => {
        setAvailableModels(config.models || [])
        setDefaultModel(config.tasks?.article?.model || '')
      })
      .catch(err => console.error('Failed to load LLM config:', err))
  }, [])

  // Load articles list
  const fetchArticles = useCallback(async () => {
    setIsLoadingList(true)
    try {
      const result = await api.getArticles({ limit: 100 })
      setArticles(result.articles)
      setTotal(result.total)
    } catch (err) {
      console.error('Failed to fetch articles:', err)
    } finally {
      setIsLoadingList(false)
    }
  }, [])

  useEffect(() => {
    fetchArticles()
  }, [fetchArticles])

  const handleGenerate = async () => {
    if (!topic.trim() || isGenerating) return
    setIsGenerating(true)
    setGenerateError(null)

    const dto: GenerateArticleDto = {
      topic: topic.trim(),
      category: category || null,
      culture: culture || null,
      model_override: modelOverride || null,
      use_scripts: useScripts,
      use_consultation_prompt: useConsultationPrompt,
      use_rag: useRag,
    }

    try {
      const result = await api.generateArticle(dto)
      setSelectedArticleId(result.article_id)
      setMode('detail')
      fetchArticles() // refresh list in background
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Ошибка при генерации статьи'
      setGenerateError(msg)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleArticleClick = (articleId: number) => {
    setSelectedArticleId(articleId)
    setMode('detail')
  }

  const handleBack = () => {
    setMode('list')
    setSelectedArticleId(null)
  }

  // Detail view
  if (mode === 'detail' && selectedArticleId !== null) {
    return (
      <div className={styles.container}>
        <ArticleView articleId={selectedArticleId} onBack={handleBack} />
      </div>
    )
  }

  // List + Form view
  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.title}>Статьи</h2>
        <p className={styles.subtitle}>Генерация и просмотр статей из базы знаний</p>
      </div>

      {/* Generation Form */}
      <div className={styles.formSection}>
        <h3 className={styles.sectionTitle}>Новая статья</h3>

        <div className={styles.field}>
          <label className={styles.label}>Тема статьи</label>
          <input
            className={styles.textInput}
            type="text"
            value={topic}
            placeholder="Например: Хлороз малины — причины и лечение"
            onChange={e => setTopic(e.target.value)}
            disabled={isGenerating}
            onKeyDown={e => { if (e.key === 'Enter') handleGenerate() }}
          />
        </div>

        <div className={styles.fieldsRow}>
          <div className={styles.field}>
            <label className={styles.label}>Категория</label>
            <select
              className={styles.select}
              value={category}
              onChange={e => { setCategory(e.target.value); savePrefs({ category: e.target.value }) }}
              disabled={isGenerating}
            >
              {CATEGORIES.map(c => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>

          <div className={styles.field}>
            <label className={styles.label}>Культура</label>
            <select
              className={styles.select}
              value={culture}
              onChange={e => { setCulture(e.target.value); savePrefs({ culture: e.target.value }) }}
              disabled={isGenerating}
            >
              {CULTURES.map(c => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>

          <div className={styles.field}>
            <label className={styles.label}>
              Модель
              {defaultModel && (
                <span className={styles.hint}>&nbsp;(сейчас: {defaultModel})</span>
              )}
            </label>
            <select
              className={styles.select}
              value={modelOverride}
              onChange={e => { setModelOverride(e.target.value); savePrefs({ modelOverride: e.target.value }) }}
              disabled={isGenerating}
            >
              <option value="">По умолчанию из настроек</option>
              {availableModels.map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        </div>

        <div className={styles.togglesRow}>
          <label className={styles.toggleLabel}>
            <input
              type="checkbox"
              className={styles.checkbox}
              checked={useScripts}
              onChange={e => { setUseScripts(e.target.checked); savePrefs({ useScripts: e.target.checked }) }}
              disabled={isGenerating}
            />
            <span>Article prompt</span>
          </label>
          <label className={styles.toggleLabel}>
            <input
              type="checkbox"
              className={styles.checkbox}
              checked={useConsultationPrompt}
              onChange={e => { setUseConsultationPrompt(e.target.checked); savePrefs({ useConsultationPrompt: e.target.checked }) }}
              disabled={isGenerating}
            />
            <span>Consultation prompt</span>
          </label>
          <label className={styles.toggleLabel}>
            <input
              type="checkbox"
              className={styles.checkbox}
              checked={useRag}
              onChange={e => { setUseRag(e.target.checked); savePrefs({ useRag: e.target.checked }) }}
              disabled={isGenerating}
            />
            <span>RAG поиск</span>
          </label>
        </div>

        {generateError && (
          <div className={styles.error}>{generateError}</div>
        )}

        <button
          className={styles.generateButton}
          onClick={handleGenerate}
          disabled={isGenerating || !topic.trim()}
        >
          {isGenerating ? (
            <>
              <span className={styles.spinner} />
              Генерация... (30–90 сек)
            </>
          ) : (
            'Сгенерировать статью'
          )}
        </button>
      </div>

      {/* Articles List */}
      <div className={styles.listSection}>
        <h3 className={styles.sectionTitle}>
          История
          {total > 0 && <span className={styles.count}>{total}</span>}
        </h3>

        {isLoadingList ? (
          <div className={styles.loading}>Загрузка...</div>
        ) : articles.length === 0 ? (
          <div className={styles.empty}>Статей пока нет. Сгенерируйте первую выше.</div>
        ) : (
          <div className={styles.articlesList}>
            {articles.map(article => (
              <button
                key={article.id}
                className={styles.articleCard}
                onClick={() => handleArticleClick(article.id)}
              >
                <div className={styles.cardTopic}>{article.topic}</div>
                <div className={styles.cardMeta}>
                  <span>{formatDate(article.created_at)}</span>
                  <span>{(article.article_length / 1000).toFixed(1)}k симв.</span>
                  {article.llm_model && <span>{article.llm_model}</span>}
                  <span>{article.rag_snippets_count} RAG</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
