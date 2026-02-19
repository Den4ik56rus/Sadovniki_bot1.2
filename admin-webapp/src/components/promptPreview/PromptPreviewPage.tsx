import { useState, useEffect, useCallback } from 'react'
import type { PromptPreviewResponse, PromptPreviewOption } from '@/types'
import { api } from '@/services/api'
import { getParam, setParams } from '@/router'
import { PromptSection } from './PromptSection'
import styles from './PromptPreviewPage.module.css'

export function PromptPreviewPage() {
  const [categories, setCategories] = useState<PromptPreviewOption[]>([])
  const [cultures, setCultures] = useState<PromptPreviewOption[]>([])
  const [selectedCategory, setSelectedCategory] = useState(() => getParam('category') || '')
  const [selectedCulture, setSelectedCulture] = useState(() => getParam('culture') || '')
  const [preview, setPreview] = useState<PromptPreviewResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Загружаем опции при монтировании
  useEffect(() => {
    const loadOptions = async () => {
      try {
        const opts = await api.getPromptPreviewOptions()
        setCategories(opts.categories)
        setCultures(opts.cultures)
        setOptionsLoaded(true)
      } catch (e) {
        setError('Не удалось загрузить опции: ' + String(e))
      }
    }
    loadOptions()
  }, [])

  // Загружаем превью при выборе обоих параметров
  const loadPreview = useCallback(async (category: string, culture: string) => {
    if (!category || !culture) return

    setIsLoading(true)
    setError(null)
    try {
      const result = await api.getPromptPreview(category, culture)
      setPreview(result)
    } catch (e) {
      setError('Ошибка загрузки превью: ' + String(e))
      setPreview(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Auto-load preview from URL params on mount (after options loaded)
  const [optionsLoaded, setOptionsLoaded] = useState(false)
  useEffect(() => {
    if (optionsLoaded && selectedCategory && selectedCulture) {
      loadPreview(selectedCategory, selectedCulture)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [optionsLoaded])

  const handleCategoryChange = (value: string) => {
    setSelectedCategory(value)
    setParams({ category: value || null, culture: selectedCulture || null })
    if (value && selectedCulture) {
      loadPreview(value, selectedCulture)
    }
  }

  const handleCultureChange = (value: string) => {
    setSelectedCulture(value)
    setParams({ category: selectedCategory || null, culture: value || null })
    if (selectedCategory && value) {
      loadPreview(selectedCategory, value)
    }
  }

  // Подсчёт активных секций
  const enabledSections = preview?.sections.filter(s => s.is_enabled !== false) ?? []
  const totalSections = preview?.sections.length ?? 0

  return (
    <div className={styles.container}>
      {/* Заголовок */}
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Превью промпта</h1>
          <p className={styles.subtitle}>
            Полный собранный промпт для консультации с аннотациями секций
          </p>
        </div>
      </header>

      {/* Ошибка */}
      {error && (
        <div className={styles.errorBanner}>
          <span>{error}</span>
          <button onClick={() => setError(null)} className={styles.errorClose}>
            ×
          </button>
        </div>
      )}

      {/* Селекторы */}
      <div className={styles.controls}>
        <div className={styles.selectGroup}>
          <label className={styles.selectLabel}>Категория</label>
          <select
            className={styles.select}
            value={selectedCategory}
            onChange={e => handleCategoryChange(e.target.value)}
          >
            <option value="">Выберите категорию...</option>
            {categories.map(c => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>

        <div className={styles.selectGroup}>
          <label className={styles.selectLabel}>Культура</label>
          <select
            className={styles.select}
            value={selectedCulture}
            onChange={e => handleCultureChange(e.target.value)}
          >
            <option value="">Выберите культуру...</option>
            {cultures.map(c => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>

        {selectedCategory && selectedCulture && (
          <button
            className={styles.refreshButton}
            onClick={() => loadPreview(selectedCategory, selectedCulture)}
            disabled={isLoading}
          >
            {isLoading ? 'Загрузка...' : 'Обновить'}
          </button>
        )}
      </div>

      {/* Метаданные */}
      {preview && (
        <div className={styles.metaBar}>
          <span className={styles.metaItem}>
            {preview.metadata.total_chars.toLocaleString()} символов
          </span>
          <span className={styles.metaSep}>|</span>
          <span className={styles.metaItem}>
            {enabledSections.length} из {totalSections} секций активны
          </span>
          {preview.metadata.culture_group && (
            <>
              <span className={styles.metaSep}>|</span>
              <span className={styles.metaItem}>
                Группа: {preview.metadata.culture_group}
              </span>
            </>
          )}
          <span className={styles.metaSep}>|</span>
          <span className={styles.metaItem}>
            База: {preview.metadata.base_source === 'db' ? 'из БД' : 'Python'}
          </span>
          <span className={styles.metaSep}>|</span>
          <span className={styles.metaItem}>
            Категория: {preview.metadata.category_source === 'db' ? 'из БД' : 'Python'}
          </span>
          {preview.metadata.use_minimal_base && (
            <>
              <span className={styles.metaSep}>|</span>
              <span className={styles.metaTag}>minimal base</span>
            </>
          )}
        </div>
      )}

      {/* Документ с секциями */}
      {isLoading && (
        <div className={styles.loadingState}>Загрузка промпта...</div>
      )}

      {!isLoading && !preview && selectedCategory && selectedCulture && !error && (
        <div className={styles.emptyState}>Нажмите "Обновить" для загрузки</div>
      )}

      {!isLoading && !preview && (!selectedCategory || !selectedCulture) && (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="6" y="6" width="36" height="36" rx="4" stroke="currentColor" strokeWidth="2"/>
              <path d="M14 16H34M14 24H28M14 32H22" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>
          <p>Выберите категорию и культуру для просмотра собранного промпта</p>
        </div>
      )}

      {preview && !isLoading && (
        <div className={styles.document}>
          {preview.sections.map(section => (
            <PromptSection
              key={section.id}
              section={section}
              onSaved={() => loadPreview(selectedCategory, selectedCulture)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
