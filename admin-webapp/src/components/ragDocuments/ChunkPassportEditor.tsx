// Chunk Passport Editor — Редактор паспортов чанков
import { useState, useEffect, useCallback, useMemo } from 'react'
import { useRagDocumentStore } from '@/store/ragDocumentStore'
import type { UpdatePassportDto } from '@/types'
import styles from './ChunkPassportEditor.module.css'

function generatePrefixPreview(passport: UpdatePassportDto): string {
  const parts: string[] = []

  const allCultures = passport.cultures || []
  const allGoals = passport.goals || []
  const allPhases = passport.growth_phases || []
  const subtypes = passport.culture_subtypes || {}

  const cultures = allCultures.filter(c => c !== 'общая')
  const goals = allGoals.filter(g => g !== 'общая')
  const phases = allPhases.filter(p => p !== 'общая')

  // Культуры
  if (cultures.length > 0) {
    const cultureParts = cultures.map(culture => {
      const subtype = subtypes[culture]
      if (subtype && subtype !== 'общая') {
        return `${culture} (${subtype})`
      }
      return culture
    })
    parts.push(`[${cultures.length === 1 ? 'Культура' : 'Культуры'}: ${cultureParts.join(', ')}]`)
  } else if (allCultures.includes('общая')) {
    parts.push('[Подходит ко всем культурам]')
  }

  // Цели
  if (goals.length > 0) {
    parts.push(`[${goals.length === 1 ? 'Цель' : 'Цели'}: ${goals.join(', ')}]`)
  } else if (allGoals.includes('общая')) {
    parts.push('[Подходит ко всем типам работ]')
  }

  // Фазы
  if (phases.length > 0) {
    parts.push(`[${phases.length === 1 ? 'Фаза' : 'Фазы'}: ${phases.join(', ')}]`)
  } else if (allPhases.includes('общая')) {
    parts.push('[Подходит ко всем фазам роста]')
  }

  return parts.join(' ') || '(пусто)'
}

export function ChunkPassportEditor() {
  const {
    currentDocument,
    chunks,
    currentChunkIndex,
    passportOptions,
    lastPassportSelection,
    isLoading,
    isUpdating,
    isGeneratingContext,
    closeEditor,
    nextChunk,
    prevChunk,
    updateChunkPassport,
    generateContext,
  } = useRagDocumentStore()

  const currentChunk = chunks[currentChunkIndex] || null

  // Локальное состояние формы
  const [passport, setPassport] = useState<UpdatePassportDto>({
    cultures: [],
    culture_subtypes: {},
    goals: [],
    growth_phases: [],
  })

  // Редактируемый текст и контекст
  const [chunkText, setChunkText] = useState('')
  const [context, setContext] = useState('')
  const [showAssembled, setShowAssembled] = useState(false)

  // Отслеживание изменений (isDirty)
  const [savedState, setSavedState] = useState<{
    passport: UpdatePassportDto
    chunkText: string
    context: string
  } | null>(null)

  const isDirty = useMemo(() => {
    if (!savedState || !currentChunk) return false

    const passportChanged =
      JSON.stringify(passport.cultures) !== JSON.stringify(savedState.passport.cultures) ||
      JSON.stringify(passport.culture_subtypes) !== JSON.stringify(savedState.passport.culture_subtypes) ||
      JSON.stringify(passport.goals) !== JSON.stringify(savedState.passport.goals) ||
      JSON.stringify(passport.growth_phases) !== JSON.stringify(savedState.passport.growth_phases)

    const textChanged = chunkText !== savedState.chunkText
    const contextChanged = context !== savedState.context

    return passportChanged || textChanged || contextChanged
  }, [passport, chunkText, context, savedState, currentChunk])

  // Получаем ID культуры по имени для фильтрации подтипов
  const getCultureId = (cultureName: string): number | null => {
    if (!cultureName || !passportOptions) return null
    const culture = passportOptions.cultures.find(c => c.name === cultureName)
    return culture?.id ?? null
  }

  // Словарь подтипов для каждой выбранной культуры
  const subtypesByCulture = useMemo(() => {
    if (!passportOptions) return {}
    const result: Record<string, Array<{ id: number; name: string }>> = {}
    for (const cultureName of passport.cultures) {
      const cultureId = getCultureId(cultureName)
      if (cultureId && passportOptions.subtypes[cultureId]?.length > 0) {
        result[cultureName] = passportOptions.subtypes[cultureId]
      }
    }
    return result
  }, [passport.cultures, passportOptions])

  // Заполняем подтипы "общая" для культур, у которых нет подтипа
  const ensureSubtypes = (cultures: string[], subtypes: Record<string, string>) => {
    const result = { ...subtypes }
    for (const culture of cultures) {
      if (!result[culture]) {
        result[culture] = 'общая'
      }
    }
    return result
  }

  // Синхронизация с текущим чанком
  useEffect(() => {
    if (currentChunk) {
      const basePassport = currentChunk.is_passported
        ? {
            cultures: currentChunk.cultures || [],
            culture_subtypes: currentChunk.culture_subtypes || {},
            goals: currentChunk.goals || [],
            growth_phases: currentChunk.growth_phases || [],
          }
        : lastPassportSelection

      const newPassport = {
        ...basePassport,
        culture_subtypes: ensureSubtypes(basePassport.cultures, basePassport.culture_subtypes || {}),
      }

      setPassport(newPassport)
      setChunkText(currentChunk.chunk_text || '')
      setContext(currentChunk.context || '')

      // Сохраняем начальное состояние (с ensureSubtypes чтобы isDirty работал корректно)
      setSavedState({
        passport: { ...newPassport },
        chunkText: currentChunk.chunk_text || '',
        context: currentChunk.context || '',
      })
    }
  }, [currentChunk, lastPassportSelection])

  // Toggle checkbox для массивов
  const toggleArrayValue = (
    field: 'cultures' | 'goals' | 'growth_phases',
    value: string
  ) => {
    setPassport(prev => {
      const arr = prev[field] || []
      const newArr = arr.includes(value)
        ? arr.filter(v => v !== value)
        : [...arr, value]

      if (field === 'cultures') {
        const newSubtypes = { ...prev.culture_subtypes }
        if (!newArr.includes(value)) {
          // Снимаем культуру — убираем её подтип
          delete newSubtypes[value]
        } else if (!newSubtypes[value]) {
          // Добавляем культуру — ставим подтип "общая" по умолчанию
          newSubtypes[value] = 'общая'
        }
        return { ...prev, [field]: newArr, culture_subtypes: newSubtypes }
      }

      return { ...prev, [field]: newArr }
    })
  }

  // Обновление подтипа для конкретной культуры
  const updateCultureSubtype = (cultureName: string, subtype: string) => {
    setPassport(prev => {
      const newSubtypes = { ...prev.culture_subtypes }
      newSubtypes[cultureName] = subtype || 'общая'
      return { ...prev, culture_subtypes: newSubtypes }
    })
  }

  // Сохранение и переход к следующему
  const handleSave = useCallback(async () => {
    if (!currentChunk) return

    const payload: UpdatePassportDto = {
      ...passport,
      chunk_text: chunkText,
      context: context,
    }

    const success = await updateChunkPassport(currentChunk.id, payload)
    if (success) {
      // Обновляем savedState после успешного сохранения
      setSavedState({
        passport: { ...passport },
        chunkText,
        context,
      })

      // Переходим к следующему чанку
      if (currentChunkIndex < chunks.length - 1) {
        nextChunk()
      }
    }
  }, [currentChunk, passport, chunkText, context, updateChunkPassport, nextChunk, currentChunkIndex, chunks.length])

  // Генерация контекста
  const handleGenerateContext = async () => {
    if (currentChunk) {
      await generateContext(currentChunk.id)
      // Обновляем локальный context из store
      const updatedChunk = chunks.find(c => c.id === currentChunk.id)
      if (updatedChunk?.context) {
        setContext(updatedChunk.context)
      }
    }
  }

  // Горячие клавиши
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Не перехватываем если фокус в textarea
      if ((e.target as HTMLElement).tagName === 'TEXTAREA') return

      if (e.key === 'ArrowRight' && e.ctrlKey) {
        handleSave()
      } else if (e.key === 'ArrowLeft' && e.ctrlKey) {
        prevChunk()
      } else if (e.key === 'Escape') {
        closeEditor()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSave, prevChunk, closeEditor])

  // Обновляем context когда меняется чанк в store
  useEffect(() => {
    if (currentChunk?.context && currentChunk.context !== context) {
      setContext(currentChunk.context)
    }
  }, [currentChunk?.context])

  if (isLoading) {
    return (
      <div className={styles.loading}>
        Загрузка чанков...
      </div>
    )
  }

  if (!currentDocument || !currentChunk) {
    return (
      <div className={styles.error}>
        <p>Документ не найден</p>
        <button onClick={closeEditor}>Назад</button>
      </div>
    )
  }

  const passportedCount = chunks.filter(c => c.is_passported).length
  const progress = Math.round((passportedCount / chunks.length) * 100)

  return (
    <div className={styles.editor}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <button className={styles.btnBack} onClick={closeEditor}>
            ← Назад
          </button>
          <h1 className={styles.title}>{currentDocument.filename}</h1>
        </div>
        <div className={styles.headerRight}>
          <div className={styles.progress}>
            <div className={styles.progressBar}>
              <div className={styles.progressFill} style={{ width: `${progress}%` }} />
            </div>
            <span className={styles.progressText}>
              {passportedCount}/{chunks.length} паспортизировано
            </span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className={styles.main}>
        {/* Left: Chunk text (editable) */}
        <div className={styles.chunkPanel}>
          <div className={styles.chunkHeader}>
            <span className={styles.chunkLabel}>
              Чанк {currentChunkIndex + 1} из {chunks.length}
              {/* Индикатор статуса */}
              <span className={`${styles.statusIndicator} ${currentChunk.is_passported ? styles.saved : ''} ${isDirty ? styles.dirty : ''}`}>
                {isDirty ? '🟡' : currentChunk.is_passported ? '✅' : '⚪'}
              </span>
            </span>
            <span className={styles.chunkSize}>
              {chunkText.length} символов
            </span>
          </div>

          <label className={styles.fieldLabel}>Текст чанка:</label>
          <textarea
            className={styles.chunkTextarea}
            value={chunkText}
            onChange={e => setChunkText(e.target.value)}
            disabled={isUpdating}
            placeholder="Текст чанка..."
          />

          {/* Context (editable) */}
          <label className={styles.fieldLabel}>Контекст (LLM):</label>
          <div className={styles.contextWrapper}>
            <textarea
              className={styles.contextTextarea}
              value={context}
              onChange={e => setContext(e.target.value)}
              disabled={isUpdating}
              placeholder="Контекст чанка (можно сгенерировать или ввести вручную)..."
            />
            <button
              className={styles.btnGenerateContext}
              onClick={handleGenerateContext}
              disabled={isGeneratingContext}
              title="Сгенерировать контекст через LLM"
            >
              {isGeneratingContext ? '⏳' : '✨'}
            </button>
          </div>

          {/* Assembled text — то что реально уходит в LLM */}
          <div className={styles.assembledSection}>
            <button
              className={styles.btnToggleAssembled}
              onClick={() => setShowAssembled(!showAssembled)}
            >
              {showAssembled ? '▼' : '▶'} Текст для LLM (prefix + context + chunk)
            </button>
            {showAssembled && (
              <pre className={styles.assembledText}>
                {currentChunk?.assembled_text || '(нет данных)'}
              </pre>
            )}
          </div>
        </div>

        {/* Right: Passport form */}
        <div className={styles.passportPanel}>
          <h3 className={styles.passportTitle}>Паспорт чанка</h3>

          {/* Культуры (checkboxes) */}
          <div className={styles.formGroup}>
            <label className={styles.groupLabel}>Культуры</label>
            <div className={styles.checkboxGrid}>
              {passportOptions?.cultures.map(c => (
                <label key={c.id} className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={passport.cultures.includes(c.name)}
                    onChange={() => toggleArrayValue('cultures', c.name)}
                    disabled={isUpdating}
                  />
                  <span>{c.name}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Подтипы для каждой выбранной культуры */}
          {Object.keys(subtypesByCulture).length > 0 && (
            <div className={styles.formGroup}>
              <label className={styles.groupLabel}>Подтипы культур</label>
              <div className={styles.subtypesGrid}>
                {Object.entries(subtypesByCulture).map(([cultureName, subtypes]) => (
                  <div key={cultureName} className={styles.subtypeRow}>
                    <span className={styles.subtypeCultureName}>{cultureName}:</span>
                    <select
                      value={passport.culture_subtypes[cultureName] || 'общая'}
                      onChange={e => updateCultureSubtype(cultureName, e.target.value)}
                      disabled={isUpdating}
                      className={styles.subtypeSelect}
                    >
                      {subtypes.map(s => (
                        <option key={s.id} value={s.name}>{s.name}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Цели (checkboxes) */}
          <div className={styles.formGroup}>
            <label className={styles.groupLabel}>Цели</label>
            <div className={styles.checkboxGrid}>
              {passportOptions?.goals.map(g => (
                <label key={g.id} className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={passport.goals.includes(g.name)}
                    onChange={() => toggleArrayValue('goals', g.name)}
                    disabled={isUpdating}
                  />
                  <span>{g.name}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Фазы роста (checkboxes) */}
          <div className={styles.formGroup}>
            <label className={styles.groupLabel}>Фазы роста</label>
            <div className={styles.checkboxGrid}>
              {passportOptions?.phases.map(p => (
                <label key={p.id} className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={passport.growth_phases.includes(p.name)}
                    onChange={() => toggleArrayValue('growth_phases', p.name)}
                    disabled={isUpdating}
                  />
                  <span>{p.name}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Prefix preview */}
          <div className={styles.prefixPreview}>
            <h4>Превью prefix:</h4>
            <code>{generatePrefixPreview(passport)}</code>
          </div>
        </div>
      </div>

      {/* Footer navigation */}
      <footer className={styles.footer}>
        <button
          className={styles.btnNav}
          onClick={prevChunk}
          disabled={currentChunkIndex === 0}
        >
          ← Предыдущий
        </button>

        <div className={styles.footerCenter}>
          {/* Индикаторы чанков */}
          <div className={styles.chunkIndicators}>
            {chunks.map((chunk, idx) => (
              <span
                key={chunk.id}
                className={`${styles.indicator} ${idx === currentChunkIndex ? styles.current : ''} ${chunk.is_passported ? styles.passported : ''}`}
                onClick={() => useRagDocumentStore.getState().setCurrentChunk(idx)}
                title={`Чанк ${idx + 1}`}
              >
                {chunk.is_passported ? '✅' : '⚪'}
              </span>
            ))}
          </div>
          <span className={styles.chunkCounter}>
            {currentChunkIndex + 1} / {chunks.length}
          </span>
        </div>

        <div className={styles.footerRight}>
          <button
            className={styles.btnSave}
            onClick={handleSave}
            disabled={isUpdating}
          >
            {isUpdating ? 'Сохранение...' : 'Сохранить →'}
          </button>
          <button
            className={styles.btnNav}
            onClick={nextChunk}
            disabled={currentChunkIndex === chunks.length - 1}
          >
            Следующий →
          </button>
        </div>
      </footer>
    </div>
  )
}
