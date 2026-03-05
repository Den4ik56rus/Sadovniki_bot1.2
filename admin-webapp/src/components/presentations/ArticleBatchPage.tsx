// ArticleBatchPage — Пакетная генерация презентаций по статьям
import { useState, useEffect, useCallback } from 'react'
import { api } from '@/services/api'
import { useArticlePresentationBatchStore } from '@/store/articlePresentationBatchStore'
import { useSSE } from '@/hooks/useSSE'
import type {
  ArticleCategoryDef,
  ArticlePresentationCultureDef,
  PresentationStyle,
  PresentationTemplate,
  ImageModelInfo,
  BatchItem,
  BatchProgressEvent,
  CreateArticlePresentationBatchDto,
} from '@/types'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './BatchPage.module.css'

type Mode = 'create' | 'history' | 'detail'

const API_BASE = import.meta.env.VITE_API_URL || '/api/admin'

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  try {
    return format(new Date(dateStr), 'd MMM yyyy, HH:mm', { locale: ru })
  } catch {
    return '—'
  }
}

function itemStatusIcon(status: string): string {
  switch (status) {
    case 'pending': return '\u23f3'
    case 'generating': return '\ud83d\udd04'
    case 'completed': return '\u2705'
    case 'failed': return '\u274c'
    case 'skipped': return '\u23ed\ufe0f'
    default: return '\u2753'
  }
}

function batchStatusLabel(status: string): string {
  switch (status) {
    case 'pending': return 'Ожидание'
    case 'running': return 'Генерация...'
    case 'completed': return 'Завершён'
    case 'cancelled': return 'Отменён'
    default: return status
  }
}

function batchStatusClass(status: string): string {
  switch (status) {
    case 'running': return styles.statusRunning
    case 'completed': return styles.statusCompleted
    case 'cancelled': return styles.statusCancelled
    case 'pending': return styles.statusPending
    default: return ''
  }
}

export function ArticleBatchPage() {
  const [mode, setMode] = useState<Mode>('create')
  const [categories, setCategories] = useState<ArticleCategoryDef[]>([])
  const [cultures, setCultures] = useState<ArticlePresentationCultureDef[]>([])
  const [stylesList, setStylesList] = useState<PresentationStyle[]>([])
  const [templatesList, setTemplatesList] = useState<PresentationTemplate[]>([])
  const [imageModels, setImageModels] = useState<ImageModelInfo[]>([])

  // Selection state: culture keys
  const [selectedCultures, setSelectedCultures] = useState<Set<string>>(new Set())
  const [includeSeasonPlan, setIncludeSeasonPlan] = useState(true)

  // Settings
  const [styleId, setStyleId] = useState<number | null>(null)
  const [templateId, setTemplateId] = useState<number | null>(null)
  const [llmModel, setLlmModel] = useState<string>('gpt-5.1')
  const [imageModel, setImageModel] = useState<string>('')

  // Batch state
  const batches = useArticlePresentationBatchStore(s => s.batches)
  const currentBatch = useArticlePresentationBatchStore(s => s.currentBatch)
  const fetchBatches = useArticlePresentationBatchStore(s => s.fetchBatches)
  const fetchBatch = useArticlePresentationBatchStore(s => s.fetchBatch)
  const cancelBatch = useArticlePresentationBatchStore(s => s.cancelBatch)
  const clearCurrentBatch = useArticlePresentationBatchStore(s => s.clearCurrentBatch)

  const [isLaunching, setIsLaunching] = useState(false)
  const [activeBatchId, setActiveBatchId] = useState<number | null>(null)

  // SSE progress
  const [progressEvent, setProgressEvent] = useState<BatchProgressEvent | null>(null)

  // Load initial data
  useEffect(() => {
    const load = async () => {
      try {
        const [defsRes, stylesRes, templatesRes, modelsRes] = await Promise.all([
          api.getArticlePresentationBatchDefinitions(),
          api.getPresentationStyles(),
          api.getPresentationTemplates(),
          api.getImageModels(),
        ])
        setCategories(defsRes.categories)
        setCultures(defsRes.cultures)
        setStylesList(stylesRes.styles)
        setTemplatesList(templatesRes.templates)
        setImageModels(modelsRes.models)
        if (modelsRes.models.length > 0) {
          const preferred = modelsRes.models.find(m => m.id.includes('3.1'))
          setImageModel(preferred ? preferred.id : modelsRes.models[0].id)
        }
      } catch (err) {
        console.error('Failed to load data:', err)
      }
    }
    load()
    fetchBatches()
  }, [])

  // SSE for active batch
  const handleSSEMessage = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data)
      setProgressEvent(data)
      if (data.type === 'batch_item_completed' || data.type === 'batch_item_failed' || data.type === 'batch_completed' || data.type === 'batch_cancelled') {
        if (activeBatchId) {
          fetchBatch(activeBatchId)
        }
      }
    } catch { /* ignore */ }
  }, [activeBatchId, fetchBatch])

  useSSE({
    endpoint: activeBatchId ? `${API_BASE.replace('/api/admin', '')}/api/admin/events/batch/${activeBatchId}` : '',
    onMessage: handleSSEMessage,
    enabled: !!activeBatchId,
  })

  // Culture key for selection (unique identifier)
  const cultureKey = (c: ArticlePresentationCultureDef) =>
    c.variety_key ? `${c.culture_key}_${c.variety_key}` : c.culture_key

  // Toggle culture selection
  const toggleCulture = (key: string) => {
    setSelectedCultures(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const selectAllCultures = () => setSelectedCultures(new Set(cultures.map(cultureKey)))
  const clearAllCultures = () => setSelectedCultures(new Set())

  // Calculate total items
  const calculateTotalItems = () => {
    let total = 0
    for (const c of cultures) {
      const key = cultureKey(c)
      if (!selectedCultures.has(key)) continue
      total += c.article_count // existing articles → presentations
      if (includeSeasonPlan) total += 1
    }
    return total
  }

  const totalItems = calculateTotalItems()

  // Launch batch
  const handleLaunch = async () => {
    if (selectedCultures.size === 0) return
    if (!confirm(`Будет сгенерировано ${totalItems} презентаций. Продолжить?`)) return

    setIsLaunching(true)
    try {
      const selectedCultureObjects = cultures
        .filter(c => selectedCultures.has(cultureKey(c)))
        .map(c => ({
          culture_key: c.culture_key,
          variety_key: c.variety_key,
        }))

      const dto: CreateArticlePresentationBatchDto = {
        cultures: selectedCultureObjects,
        include_season_plan: includeSeasonPlan,
        style_id: styleId,
        template_id: templateId,
        llm_model: llmModel || null,
        image_model: imageModel || null,
      }

      const res = await api.createArticlePresentationBatch(dto)
      setActiveBatchId(res.id)
      await fetchBatch(res.id)
      setMode('detail')
      fetchBatches()
    } catch (err) {
      console.error('Failed to create batch:', err)
      alert('Ошибка создания пакета: ' + String(err))
    } finally {
      setIsLaunching(false)
    }
  }

  // View batch detail
  const viewBatch = async (id: number) => {
    setActiveBatchId(id)
    await fetchBatch(id)
    setMode('detail')
  }

  // Build item display title
  const getItemTitle = (item: BatchItem) => {
    const culture = cultures.find(c =>
      c.culture_key === item.culture_key &&
      (c.variety_key || null) === (item.variety_key || null)
    )
    const cLabel = culture?.label || item.culture_key

    if ((item as any).is_season_plan || item.problem_key === 'season_plan') {
      return `Сезонный план — ${cLabel}`
    }

    const catKey = (item as any).category_key || item.problem_key
    const cat = categories.find(c => c.key === catKey)
    return cat ? `${cat.label} — ${cLabel}` : `${catKey} — ${cLabel}`
  }

  // ========== RENDER ==========

  // Detail view
  if (mode === 'detail' && currentBatch) {
    const batch = currentBatch
    const items = batch.items || []
    const isRunning = batch.status === 'running'
    const successPct = batch.total_items > 0 ? (batch.completed_items / batch.total_items) * 100 : 0
    const failPct = batch.total_items > 0 ? (batch.failed_items / batch.total_items) * 100 : 0

    let currentInfo = ''
    if (progressEvent && (progressEvent.type === 'batch_item_started' || progressEvent.type === 'batch_item_progress')) {
      currentInfo = progressEvent.title || ''
      if (progressEvent.slide_index !== undefined && progressEvent.slide_count) {
        currentInfo += ` (слайд ${progressEvent.slide_index + 1}/${progressEvent.slide_count})`
      }
      if (progressEvent.message) {
        currentInfo += ` — ${progressEvent.message}`
      }
    }

    return (
      <div className={styles.container}>
        <button className={styles.backButton} onClick={() => { clearCurrentBatch(); setActiveBatchId(null); setMode('create') }}>
          &larr; Назад
        </button>

        <div className={styles.header}>
          <h1 className={styles.title}>
            Пакет по статьям #{batch.id}
            <span className={`${styles.batchStatus} ${batchStatusClass(batch.status)}`} style={{ marginLeft: 12, fontSize: 14 }}>
              {batchStatusLabel(batch.status)}
            </span>
          </h1>
          <p className={styles.subtitle}>
            Создан: {formatDate(batch.created_at)}
            {batch.finished_at && ` | Завершён: ${formatDate(batch.finished_at)}`}
            {batch.total_cost_usd > 0 && ` | Стоимость: $${batch.total_cost_usd.toFixed(2)}`}
          </p>
        </div>

        <div className={styles.progressSection}>
          <div className={styles.progressHeader}>
            <span className={styles.progressTitle}>
              Прогресс: {batch.completed_items + batch.failed_items}/{batch.total_items}
            </span>
            {isRunning && (
              <button className={styles.cancelButton} onClick={() => cancelBatch(batch.id)}>
                Отменить
              </button>
            )}
          </div>

          <div className={styles.progressBar}>
            <div
              className={`${styles.progressFill} ${styles.progressFillSuccess}`}
              style={{ width: `${successPct}%`, display: 'inline-block' }}
            />
            <div
              className={`${styles.progressFill} ${styles.progressFillError}`}
              style={{ width: `${failPct}%`, display: 'inline-block' }}
            />
          </div>

          <div className={styles.progressStats}>
            <span>&#9989; Готово: {batch.completed_items}</span>
            <span>&#10060; Ошибки: {batch.failed_items}</span>
            <span>&#9203; Ожидание: {batch.total_items - batch.completed_items - batch.failed_items - (items.filter(i => i.status === 'skipped').length)}</span>
          </div>

          {currentInfo && isRunning && (
            <div className={styles.currentItem}>
              &#128296; {currentInfo}
            </div>
          )}

          <div className={styles.itemsList}>
            {items.map((item: BatchItem) => (
              <div key={item.id} className={styles.item}>
                <span className={styles.itemStatus}>{itemStatusIcon(item.status)}</span>
                <span className={styles.itemTitle}>{getItemTitle(item)}</span>
                {item.presentation_id && (
                  <span
                    className={styles.itemLink}
                    onClick={() => {
                      sessionStorage.setItem('openPresentationId', String(item.presentation_id))
                      window.location.hash = `presentations/${item.presentation_id}`
                    }}
                  >
                    &#128196; Открыть
                  </span>
                )}
                {item.error_message && (
                  <span className={styles.itemError} title={item.error_message}>
                    {item.error_message}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      {/* Tabs */}
      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${mode === 'create' ? styles.tabActive : ''}`}
          onClick={() => setMode('create')}
        >
          Новый пакет
        </button>
        <button
          className={`${styles.tab} ${mode === 'history' ? styles.tabActive : ''}`}
          onClick={() => { setMode('history'); fetchBatches() }}
        >
          История ({batches.length})
        </button>
      </div>

      {mode === 'create' && (
        <>
          {/* Selection bar */}
          <div className={styles.selectionBar}>
            <span className={styles.selectionCount}>
              Выбрано культур: {selectedCultures.size} из {cultures.length} | Презентаций: {totalItems}
            </span>
            <div className={styles.selectionActions}>
              <button className={styles.btnSelectAll} onClick={selectAllCultures}>Выбрать все</button>
              <button className={styles.btnClearAll} onClick={clearAllCultures}>Снять все</button>
            </div>
          </div>

          {/* Culture checkboxes */}
          <div className={styles.cultureGroup}>
            <div className={styles.cultureHeader} style={{ cursor: 'default' }}>
              <span className={styles.cultureTitle}>Культуры</span>
            </div>
            <div className={styles.problemsList}>
              {cultures.map(c => {
                const key = cultureKey(c)
                return (
                  <div key={key} className={styles.problemItem}>
                    <input
                      type="checkbox"
                      checked={selectedCultures.has(key)}
                      onChange={() => toggleCulture(key)}
                      id={`culture_${key}`}
                    />
                    <label htmlFor={`culture_${key}`}>
                      {c.label}
                      <span className={styles.problemHint}>
                        ({c.article_count} из {categories.length} статей)
                      </span>
                    </label>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Season plan toggle */}
          <div className={styles.cultureGroup}>
            <div className={styles.problemsList} style={{ padding: '12px 16px' }}>
              <div className={styles.problemItem}>
                <input
                  type="checkbox"
                  checked={includeSeasonPlan}
                  onChange={() => setIncludeSeasonPlan(!includeSeasonPlan)}
                  id="include_season_plan"
                />
                <label htmlFor="include_season_plan">
                  Включить сезонный план
                  <span className={styles.problemHint}>
                    (GPT читает все статьи культуры и составляет план работ по фазам роста)
                  </span>
                </label>
              </div>
            </div>
          </div>

          {/* Settings */}
          <div className={styles.settingsPanel}>
            <div className={styles.settingField}>
              <span className={styles.settingLabel}>Стиль</span>
              <select
                className={styles.settingSelect}
                value={styleId ?? ''}
                onChange={e => setStyleId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Без стиля</option>
                {stylesList.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>

            <div className={styles.settingField}>
              <span className={styles.settingLabel}>Шаблон</span>
              <select
                className={styles.settingSelect}
                value={templateId ?? ''}
                onChange={e => setTemplateId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Без шаблона</option>
                {templatesList.map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>

            <div className={styles.settingField}>
              <span className={styles.settingLabel}>LLM модель</span>
              <select
                className={styles.settingSelect}
                value={llmModel}
                onChange={e => setLlmModel(e.target.value)}
              >
                <option value="gpt-5.1">GPT-5.1</option>
                <option value="gpt-4.1">GPT-4.1</option>
                <option value="gpt-4.1-mini">GPT-4.1-mini</option>
                <option value="gpt-4o">GPT-4o</option>
                <option value="gpt-4o-mini">GPT-4o-mini</option>
              </select>
            </div>

            <div className={styles.settingField}>
              <span className={styles.settingLabel}>Модель изображений</span>
              <select
                className={styles.settingSelect}
                value={imageModel}
                onChange={e => setImageModel(e.target.value)}
              >
                {imageModels.map(m => (
                  <option key={m.id} value={m.id}>{m.name} (~${m.cost_per_image.toFixed(3)}/слайд)</option>
                ))}
              </select>
            </div>
          </div>

          {/* Launch button */}
          <button
            className={styles.launchButton}
            disabled={selectedCultures.size === 0 || isLaunching}
            onClick={handleLaunch}
          >
            {isLaunching ? 'Запуск...' : `Запустить генерацию (${totalItems} презентаций)`}
          </button>
        </>
      )}

      {mode === 'history' && (
        <div className={styles.batchList}>
          {batches.length === 0 && (
            <div className={styles.emptyState}>Пакетов пока нет</div>
          )}
          {batches.map(b => (
            <div key={b.id} className={styles.batchCard} onClick={() => viewBatch(b.id)}>
              <div className={styles.batchInfo}>
                <span className={styles.batchId}>Пакет по статьям #{b.id}</span>
                <span className={styles.batchMeta}>
                  {formatDate(b.created_at)} | {b.completed_items}/{b.total_items} готово
                  {b.failed_items > 0 && `, ${b.failed_items} ошибок`}
                  {b.total_cost_usd > 0 && ` | $${b.total_cost_usd.toFixed(2)}`}
                </span>
              </div>
              <span className={`${styles.batchStatus} ${batchStatusClass(b.status)}`}>
                {batchStatusLabel(b.status)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
