// Chunk Passport Editor — Редактор паспортов чанков
import { useState, useEffect, useCallback } from 'react'
import { useRagDocumentStore } from '@/store/ragDocumentStore'
import type { UpdatePassportDto } from '@/types'
import styles from './ChunkPassportEditor.module.css'

function generatePrefixPreview(passport: UpdatePassportDto): string {
  const parts: string[] = []

  if (passport.culture && passport.culture !== 'общая') {
    let culturePart = `[Культура: ${passport.culture}`
    if (passport.culture_subtype && passport.culture_subtype !== 'общая') {
      culturePart += `, ${passport.culture_subtype}`
    }
    culturePart += ']'
    parts.push(culturePart)
  }

  if (passport.goal && passport.goal !== 'общая') {
    parts.push(`[Цель: ${passport.goal}]`)
  }

  if (passport.growth_phase && passport.growth_phase !== 'общая') {
    parts.push(`[Фаза: ${passport.growth_phase}]`)
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
    culture: null,
    culture_subtype: null,
    goal: null,
    growth_phase: null,
  })

  // Получаем ID культуры по имени для фильтрации подтипов
  const getCultureId = (cultureName: string | null): number | null => {
    if (!cultureName || !passportOptions) return null
    const culture = passportOptions.cultures.find(c => c.name === cultureName)
    return culture?.id ?? null
  }

  const cultureId = getCultureId(passport.culture)
  const subtypes = cultureId && passportOptions?.subtypes[cultureId]
    ? passportOptions.subtypes[cultureId]
    : []

  // Синхронизация с текущим чанком
  useEffect(() => {
    if (currentChunk) {
      // Если у чанка уже есть паспорт — используем его
      if (currentChunk.is_passported) {
        setPassport({
          culture: currentChunk.culture,
          culture_subtype: currentChunk.culture_subtype,
          goal: currentChunk.goal,
          growth_phase: currentChunk.growth_phase,
        })
      } else {
        // Иначе используем последний выбор
        setPassport(lastPassportSelection)
      }
    }
  }, [currentChunk, lastPassportSelection])

  // Обработчик изменения культуры
  const handleCultureChange = (value: string) => {
    const newCulture = value || null
    setPassport(prev => ({
      ...prev,
      culture: newCulture,
      culture_subtype: null, // Сбрасываем подтип при смене культуры
    }))
  }

  // Сохранение и переход к следующему
  const handleSaveAndNext = useCallback(async () => {
    if (!currentChunk) return

    const success = await updateChunkPassport(currentChunk.id, passport)
    if (success) {
      nextChunk()
    }
  }, [currentChunk, passport, updateChunkPassport, nextChunk])

  // Только переход к следующему (без сохранения)
  const handleSkip = () => {
    nextChunk()
  }

  // Генерация контекста
  const handleGenerateContext = async () => {
    if (currentChunk) {
      await generateContext(currentChunk.id)
    }
  }

  // Горячие клавиши
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' && e.ctrlKey) {
        handleSaveAndNext()
      } else if (e.key === 'ArrowLeft' && e.ctrlKey) {
        prevChunk()
      } else if (e.key === 'Escape') {
        closeEditor()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSaveAndNext, prevChunk, closeEditor])

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
        {/* Left: Chunk text */}
        <div className={styles.chunkPanel}>
          <div className={styles.chunkHeader}>
            <span className={styles.chunkLabel}>
              Чанк {currentChunkIndex + 1} из {chunks.length}
            </span>
            <span className={styles.chunkSize}>
              {currentChunk.chunk_size} символов
            </span>
          </div>
          <div className={styles.chunkText}>
            {currentChunk.chunk_text}
          </div>

          {/* Context preview */}
          {currentChunk.context && (
            <div className={styles.contextSection}>
              <h4>Контекст (LLM):</h4>
              <p>{currentChunk.context}</p>
            </div>
          )}
        </div>

        {/* Right: Passport form */}
        <div className={styles.passportPanel}>
          <h3 className={styles.passportTitle}>Паспорт чанка</h3>

          <div className={styles.formGroup}>
            <label>Культура</label>
            <select
              value={passport.culture || ''}
              onChange={e => handleCultureChange(e.target.value)}
              disabled={isUpdating}
            >
              <option value="">— Не выбрано —</option>
              {passportOptions?.cultures.map(c => (
                <option key={c.id} value={c.name}>{c.name}</option>
              ))}
            </select>
          </div>

          {subtypes.length > 0 && (
            <div className={styles.formGroup}>
              <label>Подтип культуры</label>
              <select
                value={passport.culture_subtype || ''}
                onChange={e => setPassport(prev => ({ ...prev, culture_subtype: e.target.value || null }))}
                disabled={isUpdating}
              >
                <option value="">— Не выбрано —</option>
                {subtypes.map(s => (
                  <option key={s.id} value={s.name}>{s.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className={styles.formGroup}>
            <label>Цель</label>
            <select
              value={passport.goal || ''}
              onChange={e => setPassport(prev => ({ ...prev, goal: e.target.value || null }))}
              disabled={isUpdating}
            >
              <option value="">— Не выбрано —</option>
              {passportOptions?.goals.map(g => (
                <option key={g.id} value={g.name}>{g.name}</option>
              ))}
            </select>
          </div>

          <div className={styles.formGroup}>
            <label>Фаза роста</label>
            <select
              value={passport.growth_phase || ''}
              onChange={e => setPassport(prev => ({ ...prev, growth_phase: e.target.value || null }))}
              disabled={isUpdating}
            >
              <option value="">— Не выбрано —</option>
              {passportOptions?.phases.map(p => (
                <option key={p.id} value={p.name}>{p.name}</option>
              ))}
            </select>
          </div>

          {/* Prefix preview */}
          <div className={styles.prefixPreview}>
            <h4>Превью prefix:</h4>
            <code>{generatePrefixPreview(passport)}</code>
          </div>

          {/* Generate context button */}
          <button
            className={styles.btnGenerateContext}
            onClick={handleGenerateContext}
            disabled={isGeneratingContext}
          >
            {isGeneratingContext ? 'Генерация...' : '✨ Сгенерировать контекст'}
          </button>
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
          <span className={styles.chunkIndicator}>
            {currentChunkIndex + 1} / {chunks.length}
          </span>
        </div>

        <div className={styles.footerRight}>
          <button
            className={styles.btnSkip}
            onClick={handleSkip}
            disabled={currentChunkIndex === chunks.length - 1}
          >
            Пропустить
          </button>
          <button
            className={styles.btnSaveNext}
            onClick={handleSaveAndNext}
            disabled={isUpdating || currentChunkIndex === chunks.length - 1}
          >
            {isUpdating ? 'Сохранение...' : 'Сохранить → Следующий'}
          </button>
        </div>
      </footer>
    </div>
  )
}
