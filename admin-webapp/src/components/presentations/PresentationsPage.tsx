// Presentations Page — AI-generated slide presentations
import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '@/services/api'
import { usePresentationStore } from '@/store/presentationStore'
import type {
  CreatePresentationDto,
  PresentationProgressEvent,
  ImageModelInfo,
  CultureDef,
} from '@/types'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import { SlideViewer } from './SlideViewer'
import { StyleEditor } from './StyleEditor'
import { TemplateEditor } from './TemplateEditor'
import { GenerationProgress } from './GenerationProgress'
import styles from './PresentationsPage.module.css'

type Mode = 'list' | 'create' | 'detail' | 'slide'

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  try {
    return format(new Date(dateStr), 'd MMM yyyy, HH:mm', { locale: ru })
  } catch {
    return '—'
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'draft': return 'Черновик'
    case 'generating': return 'Генерация...'
    case 'completed': return 'Готово'
    case 'failed': return 'Ошибка'
    default: return status
  }
}

function statusClass(status: string): string {
  switch (status) {
    case 'draft': return styles.statusDraft
    case 'generating': return styles.statusGenerating
    case 'completed': return styles.statusCompleted
    case 'failed': return styles.statusFailed
    default: return ''
  }
}

const API_BASE = import.meta.env.VITE_API_URL || '/api/admin'

export function PresentationsPage() {
  const presentations = usePresentationStore(s => s.presentations)
  const total = usePresentationStore(s => s.total)
  const isLoading = usePresentationStore(s => s.isLoading)
  const fetchPresentations = usePresentationStore(s => s.fetchPresentations)
  const selectedPresentation = usePresentationStore(s => s.selectedPresentation)
  const fetchPresentation = usePresentationStore(s => s.fetchPresentation)
  const stylesList = usePresentationStore(s => s.styles)
  const fetchStyles = usePresentationStore(s => s.fetchStyles)
  const templatesList = usePresentationStore(s => s.templates)
  const fetchTemplates = usePresentationStore(s => s.fetchTemplates)
  const isGenerating = usePresentationStore(s => s.isGenerating)
  const generationProgress = usePresentationStore(s => s.generationProgress)
  const setGenerationProgress = usePresentationStore(s => s.setGenerationProgress)
  const setIsGenerating = usePresentationStore(s => s.setIsGenerating)
  const clearSelection = usePresentationStore(s => s.clearSelection)
  const completedSlides = usePresentationStore(s => s.completedSlides)
  const addCompletedSlide = usePresentationStore(s => s.addCompletedSlide)
  const clearCompletedSlides = usePresentationStore(s => s.clearCompletedSlides)

  const [mode, setMode] = useState<Mode>('list')
  const [selectedSlideId, setSelectedSlideId] = useState<number | null>(null)

  // Create form
  const [generationMode, setGenerationMode] = useState<'article' | 'problem' | 'category'>('article')
  const [title, setTitle] = useState('')
  const [sourceText, setSourceText] = useState('')
  const [styleId, setStyleId] = useState<number | null>(null)
  const [templateId, setTemplateId] = useState<number | null>(null)
  const [modelOverride, setModelOverride] = useState('')
  const [reasoningEffort, setReasoningEffort] = useState('')
  const [imageModel, setImageModel] = useState('')
  const [testMode, setTestMode] = useState(false)
  const [testSlideIndex, setTestSlideIndex] = useState(0)
  const [createError, setCreateError] = useState<string | null>(null)

  // Problem mode
  const [cultures, setCultures] = useState<CultureDef[]>([])
  const [cultureKey, setCultureKey] = useState('')
  const [varietyKey, setVarietyKey] = useState('')
  const [problemKey, setProblemKey] = useState('')

  // Category mode
  const [articleCategories, setArticleCategories] = useState<{ key: string; label: string }[]>([])
  const [articleCultures, setArticleCultures] = useState<{ culture_key: string; variety_key: string | null; label: string }[]>([])
  const [catCultureKey, setCatCultureKey] = useState('')
  const [categoryKey, setCategoryKey] = useState('')
  const [catArticleInfo, setCatArticleInfo] = useState<{ found: boolean; topic?: string; length?: number } | null>(null)
  const [catArticleText, setCatArticleText] = useState('')
  const [isLoadingArticle, setIsLoadingArticle] = useState(false)

  // System prompt
  const [defaultSystemPrompt, setDefaultSystemPrompt] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [showSystemPrompt, setShowSystemPrompt] = useState(false)

  // Models
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [imageModels, setImageModels] = useState<ImageModelInfo[]>([])

  // Style & template editors
  const [showStyleEditor, setShowStyleEditor] = useState(false)
  const [showTemplateEditor, setShowTemplateEditor] = useState(false)

  // SSE ref
  const eventSourceRef = useRef<EventSource | null>(null)

  // Load data on mount
  useEffect(() => {
    fetchPresentations()
    fetchStyles()
    fetchTemplates()
    api.getLlmConfig()
      .then(config => setAvailableModels(config.models || []))
      .catch(err => console.error('Failed to load LLM config:', err))
    api.getImageModels()
      .then(res => setImageModels(res.models || []))
      .catch(err => console.error('Failed to load image models:', err))
    api.getPresentationProblems()
      .then(res => setCultures(res.cultures || []))
      .catch(err => console.error('Failed to load problems:', err))
    api.getDefaultSystemPrompt()
      .then(res => {
        setDefaultSystemPrompt(res.system_prompt)
        setSystemPrompt(res.system_prompt)
      })
      .catch(err => console.error('Failed to load default system prompt:', err))
    api.getArticleDefinitions()
      .then(defs => {
        setArticleCategories(defs.categories || [])
        setArticleCultures(defs.cultures || [])
      })
      .catch(err => console.error('Failed to load article definitions:', err))
  }, [fetchPresentations, fetchStyles, fetchTemplates])

  // Category mode: auto-load article when culture + category selected
  useEffect(() => {
    if (generationMode !== 'category' || !catCultureKey || !categoryKey) {
      setCatArticleInfo(null)
      setCatArticleText('')
      return
    }
    const selectedCulture = articleCultures.find(c => {
      const key = c.variety_key ? `${c.culture_key}_${c.variety_key}` : c.culture_key
      return key === catCultureKey
    })
    if (!selectedCulture) return

    setIsLoadingArticle(true)
    setCatArticleInfo(null)
    api.getArticleByKeys(categoryKey, selectedCulture.culture_key, selectedCulture.variety_key)
      .then(res => {
        if (res.found && res.article) {
          setCatArticleInfo({ found: true, topic: res.article.topic, length: res.article.article_length })
          setCatArticleText(res.article.article_text)
        } else {
          setCatArticleInfo({ found: false })
          setCatArticleText('')
        }
      })
      .catch(err => {
        console.error('Failed to load article by keys:', err)
        setCatArticleInfo({ found: false })
        setCatArticleText('')
      })
      .finally(() => setIsLoadingArticle(false))
  }, [generationMode, catCultureKey, categoryKey, articleCultures])

  // SSE cleanup
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close()
    }
  }, [])

  const connectSSE = useCallback((presentationId: number) => {
    eventSourceRef.current?.close()
    const es = new EventSource(`${API_BASE}/events/presentation/${presentationId}`)

    const handleEvent = (data: PresentationProgressEvent) => {
      setGenerationProgress(data)

      // Track completed slides for live preview
      if (data.type === 'slide_completed' && data.version_id && data.slide_id !== undefined && data.slide_index !== undefined) {
        addCompletedSlide({
          slide_index: data.slide_index,
          version_id: data.version_id,
          slide_id: data.slide_id,
          slide_title: data.slide_title || `Слайд ${data.slide_index + 1}`,
        })
      }

      if (data.type === 'generation_completed' || data.type === 'generation_failed') {
        setIsGenerating(false)
        es.close()
        fetchPresentations()
        if (selectedPresentation?.id === presentationId) {
          fetchPresentation(presentationId)
        }
      }
    }

    es.onmessage = (event) => {
      try {
        handleEvent(JSON.parse(event.data))
      } catch (e) {
        console.error('SSE parse error:', e)
      }
    }

    // Listen to all event types
    const eventTypes = [
      'generation_started', 'article_generating', 'article_completed',
      'text_processing', 'slides_planned',
      'slide_generating', 'slide_completed', 'slide_failed',
      'building_pdf', 'generation_completed', 'generation_failed', 'progress',
    ]
    for (const type of eventTypes) {
      es.addEventListener(type, (event: MessageEvent) => {
        try {
          const data: PresentationProgressEvent = JSON.parse(event.data)
          data.type = type
          handleEvent(data)
        } catch (e) {
          console.error('SSE event parse error:', e)
        }
      })
    }

    es.onerror = () => {
      // Will auto-reconnect
    }

    eventSourceRef.current = es
  }, [fetchPresentations, fetchPresentation, selectedPresentation?.id, setGenerationProgress, setIsGenerating, addCompletedSlide])

  const handleCreate = async () => {
    if (generationMode === 'article') {
      if (!title.trim() || !sourceText.trim()) return
    } else if (generationMode === 'problem') {
      if (!cultureKey || !problemKey) return
    } else if (generationMode === 'category') {
      if (!catCultureKey || !categoryKey || !catArticleInfo?.found) return
    }
    setCreateError(null)

    try {
      // Передаём кастомный system prompt только если он отличается от дефолтного
      const customPrompt = systemPrompt.trim() !== defaultSystemPrompt.trim() ? systemPrompt.trim() : null

      let dto: CreatePresentationDto

      if (generationMode === 'category') {
        const selectedCulture = articleCultures.find(c => {
          const key = c.variety_key ? `${c.culture_key}_${c.variety_key}` : c.culture_key
          return key === catCultureKey
        })
        dto = {
          title: title.trim() || '',
          source_text: catArticleText,
          generation_mode: 'category',
          culture_key: selectedCulture?.culture_key || '',
          variety_key: selectedCulture?.variety_key || null,
          category_key: categoryKey,
          style_id: styleId,
          template_id: null,
          llm_model: modelOverride || null,
          reasoning_effort: reasoningEffort || null,
          image_model: imageModel || null,
          test_slide_index: testMode ? testSlideIndex : null,
          custom_system_prompt: customPrompt,
        }
      } else if (generationMode === 'problem') {
        dto = {
            title: title.trim() || '',
            source_text: '',
            generation_mode: 'problem',
            culture_key: cultureKey,
            variety_key: varietyKey || null,
            problem_key: problemKey,
            style_id: styleId,
            template_id: null,
            llm_model: modelOverride || null,
            reasoning_effort: reasoningEffort || null,
            image_model: imageModel || null,
            test_slide_index: testMode ? testSlideIndex : null,
            custom_system_prompt: customPrompt,
        }
      } else {
        dto = {
            title: title.trim(),
            source_text: sourceText.trim(),
            style_id: styleId,
            template_id: templateId,
            llm_model: modelOverride || null,
            reasoning_effort: reasoningEffort || null,
            image_model: imageModel || null,
            test_slide_index: testMode ? testSlideIndex : null,
            custom_system_prompt: customPrompt,
        }
      }

      const result = await api.createPresentation(dto)

      // Auto-start generation
      setIsGenerating(true)
      setGenerationProgress(null)
      clearCompletedSlides()
      connectSSE(result.id)
      await api.generatePresentation(result.id)

      fetchPresentation(result.id)
      setMode('detail')
      setTitle('')
      setSourceText('')
      setCultureKey('')
      setVarietyKey('')
      setProblemKey('')
      setCatCultureKey('')
      setCategoryKey('')
      setCatArticleInfo(null)
      setCatArticleText('')
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Ошибка при создании')
      setIsGenerating(false)
    }
  }

  const handleStartGeneration = async (id: number) => {
    try {
      setIsGenerating(true)
      setGenerationProgress(null)
      clearCompletedSlides()
      connectSSE(id)
      await api.generatePresentation(id)
    } catch (err) {
      setIsGenerating(false)
      console.error('Failed to start generation:', err)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить презентацию?')) return
    try {
      await api.deletePresentation(id)
      fetchPresentations()
      if (selectedPresentation?.id === id) {
        clearSelection()
        setMode('list')
      }
    } catch (err) {
      console.error('Failed to delete:', err)
    }
  }

  const handlePresentationClick = (id: number) => {
    fetchPresentation(id)
    setMode('detail')
  }

  const handleSlideClick = (slideId: number) => {
    setSelectedSlideId(slideId)
    setMode('slide')
  }

  const handleBack = () => {
    if (mode === 'slide') {
      setMode('detail')
      setSelectedSlideId(null)
      // Refresh presentation to get updated versions
      if (selectedPresentation) fetchPresentation(selectedPresentation.id)
    } else {
      setMode('list')
      clearSelection()
    }
  }

  // Slide detail view
  if (mode === 'slide' && selectedPresentation && selectedSlideId !== null) {
    const slide = selectedPresentation.slides?.find(s => s.id === selectedSlideId)
    if (slide) {
      return (
        <div className={styles.container}>
          <button className={styles.backButton} onClick={handleBack}>
            &larr; К слайдам
          </button>
          <SlideViewer
            slide={slide}
            onEdit={() => {
              if (selectedPresentation) fetchPresentation(selectedPresentation.id)
            }}
          />
        </div>
      )
    }
  }

  // Detail view
  if (mode === 'detail' && selectedPresentation) {
    return (
      <div className={styles.container}>
        <button className={styles.backButton} onClick={handleBack}>
          &larr; К списку
        </button>

        <div className={styles.detailHeader}>
          <h2 className={styles.title}>{selectedPresentation.title}</h2>
          <div className={styles.detailMeta}>
            <span className={`${styles.statusBadge} ${statusClass(selectedPresentation.status)}`}>
              {statusLabel(selectedPresentation.status)}
            </span>
            <span>{selectedPresentation.slide_count} слайдов</span>
            <span>${selectedPresentation.total_cost_usd.toFixed(4)}</span>
            <span>{formatDate(selectedPresentation.created_at)}</span>
          </div>
        </div>

        {/* Generation progress */}
        {(isGenerating || selectedPresentation.status === 'generating') && (
          <GenerationProgress progress={generationProgress} completedSlides={completedSlides} />
        )}

        {/* Error message */}
        {selectedPresentation.error_message && (
          <div className={styles.error}>{selectedPresentation.error_message}</div>
        )}

        {/* Actions */}
        <div className={styles.detailActions}>
          {selectedPresentation.status === 'draft' && (
            <button
              className={styles.generateButton}
              onClick={() => handleStartGeneration(selectedPresentation.id)}
              disabled={isGenerating}
            >
              Запустить генерацию
            </button>
          )}
          {selectedPresentation.status === 'failed' && (
            <button
              className={styles.generateButton}
              onClick={() => handleStartGeneration(selectedPresentation.id)}
              disabled={isGenerating}
            >
              Повторить генерацию
            </button>
          )}
          {selectedPresentation.pdf_path && (
            <a
              className={styles.downloadButton}
              href={api.getPresentationPdfUrl(selectedPresentation.id)}
              target="_blank"
              rel="noopener noreferrer"
            >
              Скачать PDF
            </a>
          )}
          <button
            className={styles.deleteButton}
            onClick={() => handleDelete(selectedPresentation.id)}
          >
            Удалить
          </button>
        </div>

        {/* Cost breakdown */}
        {selectedPresentation.total_cost_usd > 0 && (
          <div className={styles.costBreakdown}>
            <h4 className={styles.sectionTitle}>Стоимость</h4>
            <div className={styles.costGrid}>
              {selectedPresentation.generation_mode === 'problem' && (selectedPresentation.article_cost_usd ?? 0) > 0 && (
                <>
                  <span>Генерация статьи (GPT):</span>
                  <span>${(selectedPresentation.article_cost_usd ?? 0).toFixed(4)}</span>
                </>
              )}
              <span>Текст (GPT):</span>
              <span>${selectedPresentation.text_cost_usd.toFixed(4)}</span>
              <span>Изображения (Vertex AI):</span>
              <span>${selectedPresentation.image_cost_usd.toFixed(4)}</span>
              <span className={styles.costTotal}>Итого:</span>
              <span className={styles.costTotal}>${selectedPresentation.total_cost_usd.toFixed(4)}</span>
            </div>
          </div>
        )}

        {/* Source text (collapsible) */}
        {selectedPresentation.source_text && (
          <details className={styles.promptDetails}>
            <summary className={styles.promptSummary}>
              Текст статьи ({(selectedPresentation.source_text.length / 1000).toFixed(1)}K символов)
            </summary>
            <pre className={styles.promptText}>{selectedPresentation.source_text}</pre>
          </details>
        )}

        {/* Slide prompts (collapsible) */}
        {selectedPresentation.slides && selectedPresentation.slides.length > 0 && (
          <details className={styles.promptDetails}>
            <summary className={styles.promptSummary}>
              Промпты слайдов ({selectedPresentation.slides.length} шт.)
            </summary>
            <div className={styles.slidePromptsContainer}>
              {selectedPresentation.slides.map(slide => (
                <div key={slide.id} className={styles.slidePromptBlock}>
                  <div className={styles.slidePromptHeader}>
                    <span className={styles.slideIndex}>{slide.slide_index + 1}</span>
                    <span className={styles.slidePromptTitle}>{slide.slide_title || `Слайд ${slide.slide_index + 1}`}</span>
                  </div>
                  <pre className={styles.promptText}>{slide.slide_prompt}</pre>
                  {slide.slide_notes && (
                    <p className={styles.notesText}>{slide.slide_notes}</p>
                  )}
                </div>
              ))}
            </div>
          </details>
        )}

        {/* Custom system prompt (if used) */}
        {selectedPresentation.custom_system_prompt && (
          <details className={styles.promptDetails}>
            <summary className={styles.promptSummary}>
              System prompt (кастомный)
            </summary>
            <pre className={styles.promptText}>{selectedPresentation.custom_system_prompt}</pre>
          </details>
        )}

        {/* Slides grid */}
        {selectedPresentation.slides && selectedPresentation.slides.length > 0 && (
          <div className={styles.slidesSection}>
            <h4 className={styles.sectionTitle}>
              Слайды
              <span className={styles.count}>{selectedPresentation.slides.length}</span>
            </h4>
            <div className={styles.slidesGrid}>
              {selectedPresentation.slides.map(slide => {
                const latestVersion = slide.versions?.length
                  ? slide.versions[slide.versions.length - 1]
                  : null
                return (
                  <button
                    key={slide.id}
                    className={styles.slideCard}
                    onClick={() => handleSlideClick(slide.id)}
                  >
                    {latestVersion?.image_path ? (
                      <img
                        className={styles.slideThumb}
                        src={api.getSlideImageUrl(latestVersion.id)}
                        alt={slide.slide_title || `Слайд ${slide.slide_index + 1}`}
                      />
                    ) : (
                      <div className={styles.slidePlaceholder}>
                        {latestVersion?.status === 'generating' ? '...' : '—'}
                      </div>
                    )}
                    <div className={styles.slideInfo}>
                      <span className={styles.slideIndex}>{slide.slide_index + 1}</span>
                      <span className={styles.slideTitle}>
                        {slide.slide_title || `Слайд ${slide.slide_index + 1}`}
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>
    )
  }

  // Create form
  if (mode === 'create') {
    return (
      <div className={styles.container}>
        <button className={styles.backButton} onClick={handleBack}>
          &larr; К списку
        </button>

        <div className={styles.header}>
          <h2 className={styles.title}>Новая презентация</h2>
          <p className={styles.subtitle}>
            {generationMode === 'article'
              ? 'Загрузите текст статьи, выберите стиль — AI создаст слайды'
              : generationMode === 'problem'
              ? 'Выберите проблему — AI сгенерирует статью и создаст слайды'
              : 'Выберите категорию и культуру — презентация из готовой статьи'}
          </p>
        </div>

        <div className={styles.formSection}>
          {/* Mode toggle */}
          <div className={styles.modeTabs}>
            <button
              className={`${styles.modeTab} ${generationMode === 'article' ? styles.modeTabActive : ''}`}
              onClick={() => setGenerationMode('article')}
              disabled={isGenerating}
            >
              Текст статьи
            </button>
            <button
              className={`${styles.modeTab} ${generationMode === 'problem' ? styles.modeTabActive : ''}`}
              onClick={() => setGenerationMode('problem')}
              disabled={isGenerating}
            >
              По проблеме
            </button>
            <button
              className={`${styles.modeTab} ${generationMode === 'category' ? styles.modeTabActive : ''}`}
              onClick={() => setGenerationMode('category')}
              disabled={isGenerating}
            >
              По категории
            </button>
          </div>

          {generationMode === 'article' ? (
            <>
              <div className={styles.field}>
                <label className={styles.label}>Название</label>
                <input
                  className={styles.textInput}
                  type="text"
                  value={title}
                  placeholder="Хлороз малины — причины и лечение"
                  onChange={e => setTitle(e.target.value)}
                  disabled={isGenerating}
                />
              </div>

              <div className={styles.field}>
                <label className={styles.label}>Текст статьи</label>
                <textarea
                  className={styles.textarea}
                  value={sourceText}
                  placeholder="Вставьте текст статьи, из которой нужно сделать презентацию..."
                  onChange={e => setSourceText(e.target.value)}
                  disabled={isGenerating}
                  rows={12}
                />
              </div>
            </>
          ) : generationMode === 'problem' ? (
            <>
              {/* Problem mode: cascading selects */}
              <div className={styles.fieldsRow}>
                <div className={styles.field}>
                  <label className={styles.label}>Культура</label>
                  <select
                    className={styles.select}
                    value={cultureKey}
                    onChange={e => {
                      setCultureKey(e.target.value)
                      setVarietyKey('')
                      setProblemKey('')
                    }}
                    disabled={isGenerating}
                  >
                    <option value="">Выберите культуру...</option>
                    {cultures.map(c => (
                      <option key={c.key} value={c.key}>{c.label}</option>
                    ))}
                  </select>
                </div>

                {(() => {
                  const culture = cultures.find(c => c.key === cultureKey)
                  if (!culture || !culture.has_varieties) return null
                  return (
                    <div className={styles.field}>
                      <label className={styles.label}>Сорт</label>
                      <select
                        className={styles.select}
                        value={varietyKey}
                        onChange={e => {
                          setVarietyKey(e.target.value)
                          setProblemKey('')
                        }}
                        disabled={isGenerating}
                      >
                        <option value="">Выберите сорт...</option>
                        {culture.varieties.map(v => (
                          <option key={v.key} value={v.key}>{v.label}</option>
                        ))}
                      </select>
                    </div>
                  )
                })()}

                {(() => {
                  const culture = cultures.find(c => c.key === cultureKey)
                  if (!culture) return null
                  const needsVariety = culture.has_varieties
                  if (needsVariety && !varietyKey) return null
                  const problemsKey = needsVariety ? varietyKey : '_default'
                  const problems = culture.problems[problemsKey] || []
                  return (
                    <div className={styles.field}>
                      <label className={styles.label}>Проблема</label>
                      <select
                        className={styles.select}
                        value={problemKey}
                        onChange={e => setProblemKey(e.target.value)}
                        disabled={isGenerating}
                      >
                        <option value="">Выберите проблему...</option>
                        {problems.map(p => (
                          <option key={p.key} value={p.key}>{p.label}</option>
                        ))}
                      </select>
                    </div>
                  )
                })()}
              </div>

              <div className={styles.field}>
                <label className={styles.label}>Название (необязательно)</label>
                <input
                  className={styles.textInput}
                  type="text"
                  value={title}
                  placeholder="Автоматически из культуры и проблемы"
                  onChange={e => setTitle(e.target.value)}
                  disabled={isGenerating}
                />
              </div>
            </>
          ) : (
            <>
              {/* Category mode: culture + category selects */}
              <div className={styles.fieldsRow}>
                <div className={styles.field}>
                  <label className={styles.label}>Культура</label>
                  <select
                    className={styles.select}
                    value={catCultureKey}
                    onChange={e => {
                      setCatCultureKey(e.target.value)
                      setCatArticleInfo(null)
                      setCatArticleText('')
                    }}
                    disabled={isGenerating}
                  >
                    <option value="">Выберите культуру...</option>
                    {articleCultures.map(c => {
                      const key = c.variety_key ? `${c.culture_key}_${c.variety_key}` : c.culture_key
                      return <option key={key} value={key}>{c.label}</option>
                    })}
                  </select>
                </div>

                <div className={styles.field}>
                  <label className={styles.label}>Категория</label>
                  <select
                    className={styles.select}
                    value={categoryKey}
                    onChange={e => {
                      setCategoryKey(e.target.value)
                      setCatArticleInfo(null)
                      setCatArticleText('')
                    }}
                    disabled={isGenerating}
                  >
                    <option value="">Выберите категорию...</option>
                    {articleCategories.map(c => (
                      <option key={c.key} value={c.key}>{c.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Article status */}
              {isLoadingArticle && (
                <div className={styles.field}>
                  <span style={{ color: '#888', fontSize: 13 }}>Загрузка статьи...</span>
                </div>
              )}
              {catArticleInfo && !isLoadingArticle && (
                <div className={styles.field}>
                  {catArticleInfo.found ? (
                    <span style={{ color: '#4A7C59', fontSize: 13 }}>
                      Статья найдена: {catArticleInfo.topic} ({((catArticleInfo.length || 0) / 1000).toFixed(1)}K символов)
                    </span>
                  ) : (
                    <span style={{ color: '#C75B5B', fontSize: 13 }}>
                      Статья не найдена для этой комбинации. Сначала сгенерируйте её в пакетной генерации статей.
                    </span>
                  )}
                </div>
              )}

              <div className={styles.field}>
                <label className={styles.label}>Название (необязательно)</label>
                <input
                  className={styles.textInput}
                  type="text"
                  value={title}
                  placeholder="Автоматически из категории и культуры"
                  onChange={e => setTitle(e.target.value)}
                  disabled={isGenerating}
                />
              </div>
            </>
          )}

          <div className={styles.fieldsRow}>
            {generationMode === 'article' && (
              <div className={styles.field}>
                <label className={styles.label}>
                  Шаблон
                  <button
                    className={styles.linkButton}
                    onClick={() => setShowTemplateEditor(true)}
                  >
                    Управление
                  </button>
                </label>
                <select
                  className={styles.select}
                  value={templateId ?? ''}
                  onChange={e => setTemplateId(e.target.value ? Number(e.target.value) : null)}
                  disabled={isGenerating}
                >
                  <option value="">Без шаблона</option>
                  {templatesList.map(t => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>
            )}

            <div className={styles.field}>
              <label className={styles.label}>
                Стиль
                <button
                  className={styles.linkButton}
                  onClick={() => setShowStyleEditor(true)}
                >
                  Управление
                </button>
              </label>
              <select
                className={styles.select}
                value={styleId ?? ''}
                onChange={e => setStyleId(e.target.value ? Number(e.target.value) : null)}
                disabled={isGenerating}
              >
                <option value="">По умолчанию</option>
                {stylesList.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>

            <div className={styles.field}>
              <label className={styles.label}>Модель GPT</label>
              <select
                className={styles.select}
                value={modelOverride}
                onChange={e => setModelOverride(e.target.value)}
                disabled={isGenerating}
              >
                <option value="">По умолчанию</option>
                {availableModels.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            <div className={styles.field}>
              <label className={styles.label}>Reasoning</label>
              <select
                className={styles.select}
                value={reasoningEffort}
                onChange={e => setReasoningEffort(e.target.value)}
                disabled={isGenerating}
              >
                <option value="">Нет</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
          </div>

          {/* Image model selector */}
          <div className={styles.fieldsRow}>
            <div className={styles.field}>
              <label className={styles.label}>Модель изображений</label>
              <select
                className={styles.select}
                value={imageModel}
                onChange={e => setImageModel(e.target.value)}
                disabled={isGenerating}
              >
                <option value="">По умолчанию (Gemini 2.5 Flash)</option>
                {imageModels.map(m => (
                  <option key={m.id} value={m.id}>
                    {m.name} — ${m.cost_per_image}/слайд
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* System prompt editor */}
          <details
            className={styles.promptDetails}
            open={showSystemPrompt}
            onToggle={e => setShowSystemPrompt((e.target as HTMLDetailsElement).open)}
          >
            <summary className={styles.promptSummary}>
              System prompt для GPT
              {systemPrompt.trim() !== defaultSystemPrompt.trim() && (
                <span className={styles.promptModified}> (изменён)</span>
              )}
            </summary>
            <div style={{ padding: '0 14px 14px' }}>
              <textarea
                className={styles.textarea}
                value={systemPrompt}
                onChange={e => setSystemPrompt(e.target.value)}
                disabled={isGenerating}
                rows={16}
                style={{ fontSize: 12, fontFamily: 'monospace' }}
              />
              {systemPrompt.trim() !== defaultSystemPrompt.trim() && (
                <button
                  className={styles.linkButton}
                  style={{ marginTop: 6, fontSize: 12 }}
                  onClick={() => setSystemPrompt(defaultSystemPrompt)}
                >
                  Сбросить к дефолтному
                </button>
              )}
            </div>
          </details>

          {/* Test mode */}
          <div className={styles.testModeSection}>
            <label className={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={testMode}
                onChange={e => setTestMode(e.target.checked)}
                disabled={isGenerating}
              />
              <span>Тестовый режим (1 слайд)</span>
            </label>
            {testMode && (
              <div className={styles.testModeOptions}>
                <label className={styles.label}>Номер слайда (0 = первый)</label>
                <input
                  className={styles.textInput}
                  type="number"
                  min={0}
                  value={testSlideIndex}
                  onChange={e => setTestSlideIndex(Math.max(0, parseInt(e.target.value) || 0))}
                  disabled={isGenerating}
                  style={{ maxWidth: 120 }}
                />
                <span className={styles.testModeHint}>
                  GPT разобьёт весь текст на слайды, но изображение сгенерируется только для выбранного
                </span>
              </div>
            )}
          </div>

          {createError && <div className={styles.error}>{createError}</div>}

          <button
            className={styles.generateButton}
            onClick={handleCreate}
            disabled={isGenerating || (
              generationMode === 'article' ? (!title.trim() || !sourceText.trim()) :
              generationMode === 'problem' ? (!cultureKey || !problemKey) :
              (!catCultureKey || !categoryKey || !catArticleInfo?.found)
            )}
          >
            {isGenerating ? (
              <>
                <span className={styles.spinner} />
                {testMode ? 'Тест...' : 'Генерация...'}
              </>
            ) : (
              testMode ? 'Тест: 1 слайд' : 'Создать и сгенерировать'
            )}
          </button>
        </div>

        {/* Style Editor Modal */}
        {showStyleEditor && (
          <StyleEditor
            styles={stylesList}
            onClose={() => { setShowStyleEditor(false); fetchStyles() }}
          />
        )}

        {/* Template Editor Modal */}
        {showTemplateEditor && (
          <TemplateEditor
            templates={templatesList}
            onClose={() => { setShowTemplateEditor(false); fetchTemplates() }}
          />
        )}
      </div>
    )
  }

  // List view (default)
  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.title}>Презентации</h2>
        <p className={styles.subtitle}>AI-генерация слайдов из текста статей</p>
      </div>

      <button
        className={styles.createButton}
        onClick={() => setMode('create')}
      >
        + Новая презентация
      </button>

      {/* Generation progress (if generating) */}
      {isGenerating && generationProgress && (
        <GenerationProgress progress={generationProgress} completedSlides={completedSlides} />
      )}

      <div className={styles.listSection}>
        <h3 className={styles.sectionTitle}>
          История
          {total > 0 && <span className={styles.count}>{total}</span>}
        </h3>

        {isLoading ? (
          <div className={styles.loading}>Загрузка...</div>
        ) : presentations.length === 0 ? (
          <div className={styles.empty}>Презентаций пока нет. Создайте первую.</div>
        ) : (
          <div className={styles.presentationsList}>
            {presentations.map(pres => (
              <button
                key={pres.id}
                className={styles.presCard}
                onClick={() => handlePresentationClick(pres.id)}
              >
                <div className={styles.cardHeader}>
                  <span className={styles.cardTitle}>{pres.title}</span>
                  <span className={`${styles.statusBadge} ${statusClass(pres.status)}`}>
                    {statusLabel(pres.status)}
                  </span>
                </div>
                <div className={styles.cardMeta}>
                  <span>{pres.slide_count} слайдов</span>
                  <span>${pres.total_cost_usd.toFixed(4)}</span>
                  {pres.llm_model && <span>{pres.llm_model}</span>}
                  <span>{formatDate(pres.created_at)}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
