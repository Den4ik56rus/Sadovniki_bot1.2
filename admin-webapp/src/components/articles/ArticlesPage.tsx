// Articles Page — tabs for single article, batch generation, and culture-grouped view
import { useState, useEffect, useCallback } from 'react'
import { api } from '@/services/api'
import { ArticleView } from '@/components/crm/RightPanel/ArticleView'
import { ArticleBatchPanel } from './ArticleBatchPanel'
import { ArticleBatchDetail } from './ArticleBatchDetail'
import type { AdminArticleListItem, GenerateArticleDto } from '@/types'
import { useArticleBatchStore } from '@/store/articleBatchStore'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './ArticlesPage.module.css'

type Tab = 'single' | 'batch' | 'all'
type Mode = 'list' | 'detail' | 'batch-detail'
type GenerationMode = 'article' | 'problem_solving'

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
  { value: 'клубника летняя', label: 'Клубника летняя' },
  { value: 'клубника ремонтантная', label: 'Клубника ремонтантная' },
  { value: 'малина летняя', label: 'Малина летняя' },
  { value: 'малина ремонтантная', label: 'Малина ремонтантная' },
  { value: 'голубика', label: 'Голубика' },
  { value: 'смородина', label: 'Смородина' },
  { value: 'крыжовник', label: 'Крыжовник' },
  { value: 'ежевика', label: 'Ежевика' },
  { value: 'жимолость', label: 'Жимолость' },
]

// Culture options for "All articles" tab filtering
const CULTURE_FILTERS = [
  { culture_key: 'strawberry', variety_key: 'summer', label: 'Клубника летняя' },
  { culture_key: 'strawberry', variety_key: 'remontant', label: 'Клубника ремонтантная' },
  { culture_key: 'raspberry', variety_key: 'summer', label: 'Малина летняя' },
  { culture_key: 'raspberry', variety_key: 'remontant', label: 'Малина ремонтантная' },
  { culture_key: 'currant', variety_key: null, label: 'Смородина' },
  { culture_key: 'honeysuckle', variety_key: null, label: 'Жимолость' },
  { culture_key: 'blackberry', variety_key: null, label: 'Ежевика' },
  { culture_key: 'blueberry', variety_key: null, label: 'Голубика' },
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
  const [tab, setTab] = useState<Tab>('single')
  const [mode, setMode] = useState<Mode>('list')
  const [selectedArticleId, setSelectedArticleId] = useState<number | null>(null)
  const [activeBatchId, setActiveBatchId] = useState<number | null>(null)

  // Form state — defaults from localStorage
  const prefs = loadPrefs()
  const [generationMode, setGenerationMode] = useState<GenerationMode>(prefs.generationMode ?? 'article')
  const [topic, setTopic] = useState('')
  const [category, setCategory] = useState<string>(prefs.category ?? '')
  const [culture, setCulture] = useState<string>(prefs.culture ?? '')
  const [modelOverride, setModelOverride] = useState<string>(prefs.modelOverride ?? '')
  const [useScripts, setUseScripts] = useState<boolean>(prefs.useScripts ?? true)
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

  // Culture-filtered articles (for "all" tab)
  const [selectedCultureFilter, setSelectedCultureFilter] = useState(0)
  const [cultureArticles, setCultureArticles] = useState<AdminArticleListItem[]>([])
  const [isLoadingCultureArticles, setIsLoadingCultureArticles] = useState(false)

  // Batch store
  const batchesCount = useArticleBatchStore(s => s.batches.length)
  const fetchBatches = useArticleBatchStore(s => s.fetchBatches)

  // Load models on mount
  useEffect(() => {
    api.getLlmConfig()
      .then(config => {
        setAvailableModels(config.models || [])
        setDefaultModel(config.tasks?.article?.model || '')
      })
      .catch(err => console.error('Failed to load LLM config:', err))
    fetchBatches()
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

  // Load culture-filtered articles
  const fetchCultureArticles = useCallback(async () => {
    const filter = CULTURE_FILTERS[selectedCultureFilter]
    if (!filter) return
    setIsLoadingCultureArticles(true)
    try {
      const result = await api.getArticlesByCulture(filter.culture_key, filter.variety_key)
      setCultureArticles(result.articles)
    } catch (err) {
      console.error('Failed to fetch culture articles:', err)
    } finally {
      setIsLoadingCultureArticles(false)
    }
  }, [selectedCultureFilter])

  useEffect(() => {
    if (tab === 'all') {
      fetchCultureArticles()
    }
  }, [tab, fetchCultureArticles])

  const handleGenerate = async () => {
    if (!topic.trim() || isGenerating) return
    setIsGenerating(true)
    setGenerateError(null)

    const isProblemSolving = generationMode === 'problem_solving'

    const dto: GenerateArticleDto = {
      topic: topic.trim(),
      category: category || null,
      culture: culture || null,
      model_override: modelOverride || null,
      use_scripts: isProblemSolving ? false : useScripts,
      use_problem_solving: isProblemSolving,
      use_rag: isProblemSolving ? true : useRag,
    }

    try {
      const result = await api.generateArticle(dto)
      setSelectedArticleId(result.article_id)
      setMode('detail')
      fetchArticles()
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
    setActiveBatchId(null)
  }

  const handleBatchCreated = (batchId: number) => {
    setActiveBatchId(batchId)
    setMode('batch-detail')
  }

  const handleViewBatchDetail = (batchId: number) => {
    setActiveBatchId(batchId)
    setMode('batch-detail')
  }

  // Detail view
  if (mode === 'detail' && selectedArticleId !== null) {
    return (
      <div className={styles.container}>
        <ArticleView articleId={selectedArticleId} onBack={handleBack} />
      </div>
    )
  }

  // Batch detail view
  if (mode === 'batch-detail' && activeBatchId !== null) {
    return (
      <div className={styles.container}>
        <ArticleBatchDetail
          batchId={activeBatchId}
          onBack={handleBack}
          onArticleClick={handleArticleClick}
        />
      </div>
    )
  }

  // Main view with tabs
  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.title}>Генерация контента</h2>
        <p className={styles.subtitle}>Статьи и решения проблем на основе базы знаний</p>
      </div>

      {/* Tabs */}
      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${tab === 'single' ? styles.tabActive : ''}`}
          onClick={() => setTab('single')}
        >
          Новая статья
        </button>
        <button
          className={`${styles.tab} ${tab === 'batch' ? styles.tabActive : ''}`}
          onClick={() => { setTab('batch'); fetchBatches() }}
        >
          Пакетная генерация {batchesCount > 0 && `(${batchesCount})`}
        </button>
        <button
          className={`${styles.tab} ${tab === 'all' ? styles.tabActive : ''}`}
          onClick={() => setTab('all')}
        >
          Все статьи по культурам
        </button>
      </div>

      {/* Tab: Single article generation */}
      {tab === 'single' && (
        <>
          <div className={styles.formSection}>
            <h3 className={styles.sectionTitle}>
              {generationMode === 'problem_solving' ? 'Решение проблемы' : 'Новая статья'}
            </h3>

            <div className={styles.modeSwitcher}>
              <button
                className={`${styles.modeButton} ${generationMode === 'article' ? styles.modeButtonActive : ''}`}
                onClick={() => { setGenerationMode('article'); savePrefs({ generationMode: 'article' }) }}
                disabled={isGenerating}
              >
                Статья
              </button>
              <button
                className={`${styles.modeButton} ${generationMode === 'problem_solving' ? styles.modeButtonActive : ''}`}
                onClick={() => { setGenerationMode('problem_solving'); savePrefs({ generationMode: 'problem_solving' }) }}
                disabled={isGenerating}
              >
                Решение проблемы
              </button>
            </div>

            <div className={styles.field}>
              <label className={styles.label}>
                {generationMode === 'problem_solving' ? 'Описание проблемы' : 'Тема статьи'}
              </label>
              <input
                className={styles.textInput}
                type="text"
                value={topic}
                placeholder={generationMode === 'problem_solving'
                  ? 'Опишите проблему: Хлороз малины — листья желтеют'
                  : 'Например: Хлороз малины — причины и лечение'}
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

            {generationMode === 'article' && (
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
                    checked={useRag}
                    onChange={e => { setUseRag(e.target.checked); savePrefs({ useRag: e.target.checked }) }}
                    disabled={isGenerating}
                  />
                  <span>RAG поиск</span>
                </label>
              </div>
            )}

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
                  Генерация... (30-90 сек)
                </>
              ) : (
                generationMode === 'problem_solving' ? 'Сгенерировать решение' : 'Сгенерировать статью'
              )}
            </button>
          </div>

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
        </>
      )}

      {/* Tab: Batch generation */}
      {tab === 'batch' && (
        <ArticleBatchPanel
          onBatchCreated={handleBatchCreated}
          onViewBatch={handleViewBatchDetail}
        />
      )}

      {/* Tab: All articles by culture */}
      {tab === 'all' && (
        <div>
          <div className={styles.cultureFilterRow}>
            {CULTURE_FILTERS.map((cf, idx) => (
              <button
                key={`${cf.culture_key}_${cf.variety_key || ''}`}
                className={`${styles.cultureFilterBtn} ${idx === selectedCultureFilter ? styles.cultureFilterBtnActive : ''}`}
                onClick={() => setSelectedCultureFilter(idx)}
              >
                {cf.label}
              </button>
            ))}
          </div>

          {isLoadingCultureArticles ? (
            <div className={styles.loading}>Загрузка...</div>
          ) : cultureArticles.length === 0 ? (
            <div className={styles.empty}>
              Нет статей для &laquo;{CULTURE_FILTERS[selectedCultureFilter]?.label}&raquo;.
              Запустите пакетную генерацию.
            </div>
          ) : (
            <div className={styles.articlesList}>
              {cultureArticles.map(article => (
                <button
                  key={article.id}
                  className={styles.articleCard}
                  onClick={() => handleArticleClick(article.id)}
                >
                  <div className={styles.cardTopic}>{article.topic}</div>
                  <div className={styles.cardMeta}>
                    <span>{formatDate(article.created_at)}</span>
                    <span>{((article.article_length || 0) / 1000).toFixed(1)}k симв.</span>
                    {article.llm_model && <span>{article.llm_model}</span>}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
