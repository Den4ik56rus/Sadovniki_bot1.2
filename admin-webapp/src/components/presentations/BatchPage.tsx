// BatchPage — Пакетная генерация презентаций
import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '@/services/api'
import { useBatchStore } from '@/store/batchStore'
import { usePresentationStore } from '@/store/presentationStore'
import { useSSE } from '@/hooks/useSSE'
import type {
  CultureDef,
  PresentationStyle,
  PresentationTemplate,
  ImageModelInfo,
  BatchItem,
  BatchProgressEvent,
  CreateBatchDto,
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

export function BatchPage() {
  const [mode, setMode] = useState<Mode>('create')
  const [cultures, setCultures] = useState<CultureDef[]>([])
  const [stylesList, setStylesList] = useState<PresentationStyle[]>([])
  const [templatesList, setTemplatesList] = useState<PresentationTemplate[]>([])
  const [imageModels, setImageModels] = useState<ImageModelInfo[]>([])

  // Selection state
  const [selected, setSelected] = useState<Set<string>>(new Set()) // problem_key set
  const [expandedCultures, setExpandedCultures] = useState<Set<string>>(new Set())

  // Settings
  const [styleId, setStyleId] = useState<number | null>(null)
  const [templateId, setTemplateId] = useState<number | null>(null)
  const [llmModel, setLlmModel] = useState<string>('gpt-4o')
  const [imageModel, setImageModel] = useState<string>('')

  // Batch state
  const batches = useBatchStore(s => s.batches)
  const currentBatch = useBatchStore(s => s.currentBatch)
  const fetchBatches = useBatchStore(s => s.fetchBatches)
  const fetchBatch = useBatchStore(s => s.fetchBatch)
  const cancelBatch = useBatchStore(s => s.cancelBatch)
  const clearCurrentBatch = useBatchStore(s => s.clearCurrentBatch)

  const [isLaunching, setIsLaunching] = useState(false)
  const [activeBatchId, setActiveBatchId] = useState<number | null>(null)

  // SSE progress
  const [progressEvent, setProgressEvent] = useState<BatchProgressEvent | null>(null)
  const progressRef = useRef<BatchProgressEvent | null>(null)

  // Load initial data
  useEffect(() => {
    const load = async () => {
      try {
        const [problemsRes, stylesRes, templatesRes, modelsRes] = await Promise.all([
          api.getPresentationProblems(),
          api.getPresentationStyles(),
          api.getPresentationTemplates(),
          api.getImageModels(),
        ])
        setCultures(problemsRes.cultures)
        setStylesList(stylesRes.styles)
        setTemplatesList(templatesRes.templates)
        setImageModels(modelsRes.models)
        if (modelsRes.models.length > 0) {
          setImageModel(modelsRes.models[0].id)
        }
        // Expand all cultures by default
        const allKeys = new Set<string>()
        problemsRes.cultures.forEach(c => {
          if (c.has_varieties) {
            c.varieties.forEach(v => allKeys.add(`${c.key}_${v.key}`))
          } else {
            allKeys.add(c.key)
          }
        })
        setExpandedCultures(allKeys)
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
      progressRef.current = data

      // Refresh batch detail on completion events
      if (data.type === 'batch_item_completed' || data.type === 'batch_item_failed' || data.type === 'batch_completed' || data.type === 'batch_cancelled') {
        if (activeBatchId) {
          fetchBatch(activeBatchId)
        }
      }
    } catch { /* ignore parse errors */ }
  }, [activeBatchId, fetchBatch])

  useSSE({
    endpoint: activeBatchId ? `${API_BASE.replace('/api/admin', '')}/api/admin/events/batch/${activeBatchId}` : '',
    onMessage: handleSSEMessage,
    enabled: !!activeBatchId,
  })

  // Helper: get all problem keys with their culture/variety info
  const getAllProblems = useCallback(() => {
    const items: { culture_key: string; variety_key: string | null; problem_key: string; label: string; hint?: string | null; cultureLabel: string }[] = []
    cultures.forEach(c => {
      if (c.has_varieties) {
        c.varieties.forEach(v => {
          const problems = c.problems[v.key] || []
          problems.forEach(p => {
            items.push({
              culture_key: c.key,
              variety_key: v.key,
              problem_key: p.key,
              label: p.label,
              hint: p.hint,
              cultureLabel: `${c.label} ${v.label.toLowerCase()}`,
            })
          })
        })
      } else {
        const problems = c.problems['_default'] || c.problems[Object.keys(c.problems)[0]] || []
        problems.forEach(p => {
          items.push({
            culture_key: c.key,
            variety_key: null,
            problem_key: p.key,
            label: p.label,
            hint: p.hint,
            cultureLabel: c.label,
          })
        })
      }
    })
    return items
  }, [cultures])

  const allProblems = getAllProblems()
  const totalProblems = allProblems.length

  // Toggle problem selection
  const toggleProblem = (key: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // Toggle all problems in a culture group
  const toggleCultureGroup = (groupKey: string) => {
    const groupProblems = allProblems.filter(p => {
      const gk = p.culture_key + (p.variety_key ? `_${p.variety_key}` : '')
      return gk === groupKey
    })
    const allSelected = groupProblems.every(p => selected.has(p.problem_key))
    setSelected(prev => {
      const next = new Set(prev)
      groupProblems.forEach(p => {
        if (allSelected) next.delete(p.problem_key)
        else next.add(p.problem_key)
      })
      return next
    })
  }

  // Select all / clear all
  const selectAll = () => setSelected(new Set(allProblems.map(p => p.problem_key)))
  const clearAll = () => setSelected(new Set())

  // Toggle expand
  const toggleExpand = (key: string) => {
    setExpandedCultures(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // Launch batch
  const handleLaunch = async () => {
    if (selected.size === 0) return
    if (!confirm(`Будет сгенерировано ${selected.size} презентаций. Продолжить?`)) return

    setIsLaunching(true)
    try {
      const items = allProblems
        .filter(p => selected.has(p.problem_key))
        .map(p => ({
          culture_key: p.culture_key,
          variety_key: p.variety_key,
          problem_key: p.problem_key,
        }))

      const dto: CreateBatchDto = {
        items,
        style_id: styleId,
        template_id: templateId,
        llm_model: llmModel || null,
        image_model: imageModel || null,
      }

      const res = await api.createBatch(dto)
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

  // Build culture groups for display
  const cultureGroups: { key: string; label: string; problems: typeof allProblems }[] = []
  cultures.forEach(c => {
    if (c.has_varieties) {
      c.varieties.forEach(v => {
        const groupKey = `${c.key}_${v.key}`
        const problems = allProblems.filter(p => p.culture_key === c.key && p.variety_key === v.key)
        if (problems.length > 0) {
          cultureGroups.push({ key: groupKey, label: `${c.label} ${v.label.toLowerCase()}`, problems })
        }
      })
    } else {
      const problems = allProblems.filter(p => p.culture_key === c.key)
      if (problems.length > 0) {
        cultureGroups.push({ key: c.key, label: c.label, problems })
      }
    }
  })

  // ========== RENDER ==========

  // Detail view
  if (mode === 'detail' && currentBatch) {
    const batch = currentBatch
    const items = batch.items || []
    const isRunning = batch.status === 'running'
    const successPct = batch.total_items > 0 ? (batch.completed_items / batch.total_items) * 100 : 0
    const failPct = batch.total_items > 0 ? (batch.failed_items / batch.total_items) * 100 : 0

    // Current generating item info from progress event
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
            Пакет #{batch.id}
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

        {/* Progress bar */}
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

          {/* Items list */}
          <div className={styles.itemsList}>
            {items.map((item: BatchItem) => {
              const cLabel = allProblems.find(p => p.problem_key === item.problem_key)
              const displayTitle = cLabel
                ? `${cLabel.cultureLabel} — ${cLabel.label}`
                : `${item.culture_key}/${item.problem_key}`

              return (
                <div key={item.id} className={styles.item}>
                  <span className={styles.itemStatus}>{itemStatusIcon(item.status)}</span>
                  <span className={styles.itemTitle}>{displayTitle}</span>
                  {item.presentation_id && (
                    <span
                      className={styles.itemLink}
                      onClick={() => {
                        // Navigate to presentation detail in existing PresentationsPage
                        const { setView } = (window as any).__uiStore || {}
                        if (setView) setView('presentations')
                        // Store the ID to open
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
              )
            })}
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
              Выбрано: {selected.size} из {totalProblems}
            </span>
            <div className={styles.selectionActions}>
              <button className={styles.btnSelectAll} onClick={selectAll}>Выбрать все</button>
              <button className={styles.btnClearAll} onClick={clearAll}>Снять все</button>
            </div>
          </div>

          {/* Culture groups */}
          {cultureGroups.map(group => {
            const isExpanded = expandedCultures.has(group.key)
            const selectedInGroup = group.problems.filter(p => selected.has(p.problem_key)).length

            return (
              <div key={group.key} className={styles.cultureGroup}>
                <div
                  className={styles.cultureHeader}
                  onClick={() => toggleExpand(group.key)}
                >
                  <span>
                    <span className={styles.cultureTitle}>{group.label}</span>
                    <span className={styles.cultureCount}>
                      ({selectedInGroup}/{group.problems.length})
                    </span>
                  </span>
                  <button
                    className={styles.cultureCheckAll}
                    onClick={(e) => { e.stopPropagation(); toggleCultureGroup(group.key) }}
                  >
                    {selectedInGroup === group.problems.length ? 'Снять все' : 'Выбрать все'}
                  </button>
                </div>
                {isExpanded && (
                  <div className={styles.problemsList}>
                    {group.problems.map(p => (
                      <div key={p.problem_key} className={styles.problemItem}>
                        <input
                          type="checkbox"
                          checked={selected.has(p.problem_key)}
                          onChange={() => toggleProblem(p.problem_key)}
                          id={`prob_${p.problem_key}`}
                        />
                        <label htmlFor={`prob_${p.problem_key}`}>
                          {p.label}
                          {p.hint && <span className={styles.problemHint}>({p.hint})</span>}
                        </label>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}

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
            disabled={selected.size === 0 || isLaunching}
            onClick={handleLaunch}
          >
            {isLaunching ? 'Запуск...' : `Запустить генерацию (${selected.size} презентаций)`}
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
                <span className={styles.batchId}>Пакет #{b.id}</span>
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
