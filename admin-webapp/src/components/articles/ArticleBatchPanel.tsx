// ArticleBatchPanel — create batch + history list
import { useState, useEffect } from 'react'
import { api } from '@/services/api'
import { useArticleBatchStore } from '@/store/articleBatchStore'
import type { ArticleCategoryDef, ArticleCultureDef, ArticleBatchListItem } from '@/types'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './ArticleBatchPanel.module.css'

interface Props {
  onBatchCreated: (batchId: number) => void
  onViewBatch: (batchId: number) => void
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  try {
    return format(new Date(dateStr), 'd MMM yyyy, HH:mm', { locale: ru })
  } catch {
    return '—'
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

type SubMode = 'create' | 'history'

export function ArticleBatchPanel({ onBatchCreated, onViewBatch }: Props) {
  const [subMode, setSubMode] = useState<SubMode>('create')

  // Definitions
  const [categories, setCategories] = useState<ArticleCategoryDef[]>([])
  const [cultures, setCultures] = useState<ArticleCultureDef[]>([])

  // Selection: Set of "culture_key:variety_key:category_key"
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())

  // Settings
  const [llmModel, setLlmModel] = useState<string>('gpt-5.1')
  const [reasoningEffort, setReasoningEffort] = useState<string>('')
  const [isLaunching, setIsLaunching] = useState(false)

  // Store
  const batches = useArticleBatchStore(s => s.batches)
  const fetchBatches = useArticleBatchStore(s => s.fetchBatches)

  // Load definitions
  useEffect(() => {
    api.getArticleDefinitions()
      .then(defs => {
        setCategories(defs.categories)
        setCultures(defs.cultures)
        // Expand all groups by default
        const keys = new Set<string>()
        defs.cultures.forEach(c => keys.add(`${c.culture_key}:${c.variety_key || ''}`))
        setExpandedGroups(keys)
      })
      .catch(err => console.error('Failed to load definitions:', err))
  }, [])

  const makeKey = (cultureKey: string, varietyKey: string | null, categoryKey: string) =>
    `${cultureKey}:${varietyKey || ''}:${categoryKey}`

  const makeCultureGroupKey = (c: ArticleCultureDef) => `${c.culture_key}:${c.variety_key || ''}`

  const totalPossible = cultures.length * categories.length

  // Toggle individual item
  const toggleItem = (key: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // Toggle all categories for a culture
  const toggleCultureGroup = (culture: ArticleCultureDef) => {
    const keys = categories.map(cat => makeKey(culture.culture_key, culture.variety_key, cat.key))
    const allSelected = keys.every(k => selected.has(k))
    setSelected(prev => {
      const next = new Set(prev)
      keys.forEach(k => {
        if (allSelected) next.delete(k)
        else next.add(k)
      })
      return next
    })
  }

  const selectAll = () => {
    const all = new Set<string>()
    cultures.forEach(c => {
      categories.forEach(cat => {
        all.add(makeKey(c.culture_key, c.variety_key, cat.key))
      })
    })
    setSelected(all)
  }

  const clearAll = () => setSelected(new Set())

  const toggleExpand = (key: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // Launch batch
  const handleLaunch = async () => {
    if (selected.size === 0) return
    if (!confirm(`Будет сгенерировано ${selected.size} статей. Продолжить?`)) return

    setIsLaunching(true)
    try {
      const items = Array.from(selected).map(key => {
        const [culture_key, variety_key, category_key] = key.split(':')
        return {
          culture_key,
          variety_key: variety_key || null,
          category_key,
        }
      })

      const res = await api.createArticleBatch({
        items,
        llm_model: llmModel || null,
        reasoning_effort: reasoningEffort || null,
      })

      onBatchCreated(res.id)
      fetchBatches()
    } catch (err) {
      console.error('Failed to create article batch:', err)
      alert('Ошибка создания пакета: ' + String(err))
    } finally {
      setIsLaunching(false)
    }
  }

  return (
    <div>
      {/* Sub-tabs */}
      <div className={styles.subTabs}>
        <button
          className={`${styles.subTab} ${subMode === 'create' ? styles.subTabActive : ''}`}
          onClick={() => setSubMode('create')}
        >
          Новый пакет
        </button>
        <button
          className={`${styles.subTab} ${subMode === 'history' ? styles.subTabActive : ''}`}
          onClick={() => { setSubMode('history'); fetchBatches() }}
        >
          История ({batches.length})
        </button>
      </div>

      {subMode === 'create' && (
        <>
          {/* Selection bar */}
          <div className={styles.selectionBar}>
            <span className={styles.selectionCount}>
              Выбрано: {selected.size} из {totalPossible}
            </span>
            <div className={styles.selectionActions}>
              <button className={styles.btnAction} onClick={selectAll}>Выбрать все</button>
              <button className={styles.btnAction} onClick={clearAll}>Снять все</button>
            </div>
          </div>

          {/* Culture groups */}
          {cultures.map(culture => {
            const groupKey = makeCultureGroupKey(culture)
            const isExpanded = expandedGroups.has(groupKey)
            const selectedInGroup = categories.filter(cat =>
              selected.has(makeKey(culture.culture_key, culture.variety_key, cat.key))
            ).length

            return (
              <div key={groupKey} className={styles.cultureGroup}>
                <div
                  className={styles.cultureHeader}
                  onClick={() => toggleExpand(groupKey)}
                >
                  <span>
                    <span className={styles.cultureTitle}>{culture.label}</span>
                    <span className={styles.cultureCount}>
                      ({selectedInGroup}/{categories.length})
                    </span>
                  </span>
                  <button
                    className={styles.cultureCheckAll}
                    onClick={(e) => { e.stopPropagation(); toggleCultureGroup(culture) }}
                  >
                    {selectedInGroup === categories.length ? 'Снять все' : 'Выбрать все'}
                  </button>
                </div>
                {isExpanded && (
                  <div className={styles.categoryList}>
                    {categories.map(cat => {
                      const key = makeKey(culture.culture_key, culture.variety_key, cat.key)
                      return (
                        <div key={cat.key} className={styles.categoryItem}>
                          <input
                            type="checkbox"
                            checked={selected.has(key)}
                            onChange={() => toggleItem(key)}
                            id={`art_${groupKey}_${cat.key}`}
                          />
                          <label htmlFor={`art_${groupKey}_${cat.key}`}>
                            {cat.label}
                          </label>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}

          {/* Settings */}
          <div className={styles.settingsPanel}>
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
              <span className={styles.settingLabel}>Reasoning (думать)</span>
              <select
                className={styles.settingSelect}
                value={reasoningEffort}
                onChange={e => setReasoningEffort(e.target.value)}
              >
                <option value="">Из настроек (по умолчанию)</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
          </div>

          {/* Launch button */}
          <button
            className={styles.launchButton}
            disabled={selected.size === 0 || isLaunching}
            onClick={handleLaunch}
          >
            {isLaunching ? 'Запуск...' : `Запустить генерацию (${selected.size} статей)`}
          </button>
        </>
      )}

      {subMode === 'history' && (
        <div className={styles.batchList}>
          {batches.length === 0 && (
            <div className={styles.emptyState}>Пакетов пока нет</div>
          )}
          {batches.map((b: ArticleBatchListItem) => (
            <div key={b.id} className={styles.batchCard} onClick={() => onViewBatch(b.id)}>
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
