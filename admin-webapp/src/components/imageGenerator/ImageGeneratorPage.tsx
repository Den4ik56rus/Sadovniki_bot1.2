import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '@/services/api'
import { useImageGeneratorStore } from '@/store/imageGeneratorStore'
import type { ImageGeneration } from '@/types'
import styles from './ImageGeneratorPage.module.css'

const API_BASE = import.meta.env.VITE_API_URL || '/api/admin'
const ITEMS_PER_PAGE = 20

export function ImageGeneratorPage() {
  const {
    generations, total, isLoading,
    presets, fetchHistory, fetchPresets,
    currentGeneration, setCurrentGeneration,
    isGenerating, setIsGenerating,
    deleteGeneration,
  } = useImageGeneratorStore()

  // Form state
  const [userPrompt, setUserPrompt] = useState('')
  const [selectedPreset, setSelectedPreset] = useState('photo')
  const [referencePath, setReferencePath] = useState<string | null>(null)
  const [referencePreviewUrl, setReferencePreviewUrl] = useState<string | null>(null)
  const [optimizedPrompt, setOptimizedPrompt] = useState('')
  const [showOptimized, setShowOptimized] = useState(false)
  const [useOptimization, setUseOptimization] = useState(false)
  const [progressMessage, setProgressMessage] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [resultImagePath, setResultImagePath] = useState<string | null>(null)
  const [resultCost, setResultCost] = useState<number | null>(null)
  const [page, setPage] = useState(0)
  const [expandedGen, setExpandedGen] = useState<ImageGeneration | null>(null)
  const [uploading, setUploading] = useState(false)

  // Edit mode state
  const [editingImagePath, setEditingImagePath] = useState<string | null>(null)
  const [editPrompt, setEditPrompt] = useState('')

  const fileInputRef = useRef<HTMLInputElement>(null)
  const sseRef = useRef<EventSource | null>(null)

  useEffect(() => {
    fetchPresets()
    fetchHistory({ limit: ITEMS_PER_PAGE, offset: 0 })
  }, [fetchPresets, fetchHistory])

  // SSE connection
  const connectSSE = useCallback((genId: number) => {
    if (sseRef.current) sseRef.current.close()

    const source = new EventSource(`${API_BASE}/events/image-generator/${genId}`)
    sseRef.current = source

    source.addEventListener('status', (e) => {
      const data = JSON.parse(e.data)
      setProgressMessage(data.message || data.status)
    })

    source.addEventListener('optimized', (e) => {
      const data = JSON.parse(e.data)
      setOptimizedPrompt(data.optimized_prompt || '')
      setShowOptimized(true)
      setProgressMessage(data.message || 'Промпт оптимизирован')
    })

    source.addEventListener('completed', (e) => {
      const data = JSON.parse(e.data)
      setResultImagePath(data.image_path)
      setResultCost(data.cost_usd)
      setIsGenerating(false)
      setProgressMessage('')
      fetchHistory({ limit: ITEMS_PER_PAGE, offset: page * ITEMS_PER_PAGE })
      source.close()
      sseRef.current = null
    })

    source.addEventListener('failed', (e) => {
      const data = JSON.parse(e.data)
      setErrorMessage(data.error || 'Ошибка генерации')
      setIsGenerating(false)
      setProgressMessage('')
      source.close()
      sseRef.current = null
    })

    source.onerror = () => {
      source.close()
      sseRef.current = null
    }
  }, [setIsGenerating, fetchHistory, page])

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      if (sseRef.current) sseRef.current.close()
    }
  }, [])

  const handleGenerate = async () => {
    if (!userPrompt.trim()) return
    setErrorMessage('')
    setResultImagePath(null)
    setResultCost(null)
    setOptimizedPrompt('')
    setShowOptimized(false)
    setIsGenerating(true)
    setProgressMessage('Запуск...')

    try {
      const result = await api.generateImage({
        user_prompt: userPrompt.trim(),
        preset: selectedPreset,
        reference_image_path: referencePath || undefined,
        optimize_prompt: useOptimization,
      })
      setCurrentGeneration(result.generation)
      connectSSE(result.id)
    } catch (err) {
      setErrorMessage(String(err))
      setIsGenerating(false)
      setProgressMessage('')
    }
  }

  const handleGenerateDirect = async () => {
    if (!optimizedPrompt.trim() || !currentGeneration) return
    setErrorMessage('')
    setResultImagePath(null)
    setResultCost(null)
    setIsGenerating(true)
    setProgressMessage('Генерация изображения...')

    try {
      await api.generateImageDirect(currentGeneration.id, optimizedPrompt.trim())
      connectSSE(currentGeneration.id)
    } catch (err) {
      setErrorMessage(String(err))
      setIsGenerating(false)
      setProgressMessage('')
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const result = await api.uploadReferenceImage(file)
      setReferencePath(result.reference_path)
      setReferencePreviewUrl(`${API_BASE}/image-generator/image/${result.reference_path}`)
    } catch (err) {
      setErrorMessage(`Ошибка загрузки: ${err}`)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const removeReference = () => {
    setReferencePath(null)
    setReferencePreviewUrl(null)
  }

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    fetchHistory({ limit: ITEMS_PER_PAGE, offset: newPage * ITEMS_PER_PAGE })
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить эту генерацию?')) return
    const ok = await deleteGeneration(id)
    if (ok) setExpandedGen(null)
  }

  const handleDownload = (imagePath: string) => {
    const link = document.createElement('a')
    link.href = `${API_BASE}/image-generator/image/${imagePath}`
    link.download = imagePath
    link.click()
  }

  const startEditImage = (imagePath: string) => {
    setEditingImagePath(imagePath)
    setEditPrompt('')
    setExpandedGen(null)
  }

  const cancelEdit = () => {
    setEditingImagePath(null)
    setEditPrompt('')
  }

  const handleEditSubmit = async () => {
    if (!editPrompt.trim() || !editingImagePath) return
    setErrorMessage('')
    setResultImagePath(null)
    setResultCost(null)
    setOptimizedPrompt('')
    setShowOptimized(false)
    setIsGenerating(true)
    setProgressMessage('Запуск редактирования...')

    try {
      const result = await api.generateImage({
        user_prompt: editPrompt.trim(),
        preset: 'edit',
        reference_image_path: editingImagePath,
        optimize_prompt: false,
      })
      setCurrentGeneration(result.generation)
      connectSSE(result.id)
      setEditingImagePath(null)
      setEditPrompt('')
    } catch (err) {
      setErrorMessage(String(err))
      setIsGenerating(false)
      setProgressMessage('')
    }
  }

  const getPresetLabel = (key: string) => {
    const p = presets.find((pr) => pr.key === key)
    return p?.label || key
  }

  const totalPages = Math.ceil(total / ITEMS_PER_PAGE)

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>Генератор картинок</h1>
        <p className={styles.subtitle}>
          AI-генерация изображений через Nano Banana Pro (Vertex AI)
        </p>
      </div>

      {/* Generator Section */}
      <div className={styles.generatorSection}>
        <h2 className={styles.sectionTitle}>Создать изображение</h2>

        <textarea
          className={styles.promptInput}
          value={userPrompt}
          onChange={(e) => setUserPrompt(e.target.value)}
          placeholder="Опишите что хотите увидеть... (на русском или английском)"
          disabled={isGenerating}
        />

        {/* Preset Chips */}
        <div className={styles.presetsRow}>
          {presets.map((preset) => (
            <button
              key={preset.key}
              className={`${styles.presetChip} ${selectedPreset === preset.key ? styles.presetChipActive : ''}`}
              onClick={() => setSelectedPreset(preset.key)}
              disabled={isGenerating}
              title={preset.description}
            >
              {preset.label}
            </button>
          ))}
        </div>

        {/* Reference Upload */}
        <div className={styles.referenceRow}>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={handleFileUpload}
          />
          <button
            className={styles.uploadButton}
            onClick={() => fileInputRef.current?.click()}
            disabled={isGenerating || uploading}
          >
            {uploading ? 'Загрузка...' : '+ Референс-фото'}
          </button>
          {referencePreviewUrl && (
            <>
              <img src={referencePreviewUrl} alt="Референс" className={styles.refPreview} />
              <button className={styles.removeRef} onClick={removeReference} title="Убрать референс">
                &times;
              </button>
            </>
          )}
          {selectedPreset === 'edit' && !referencePath && (
            <span style={{ fontSize: 12, color: 'var(--accent-yellow, #F59E0B)' }}>
              Для редактирования загрузите фото
            </span>
          )}
        </div>

        {/* Optimize Prompt Checkbox */}
        <label className={styles.optimizeCheckbox}>
          <input
            type="checkbox"
            checked={useOptimization}
            onChange={(e) => setUseOptimization(e.target.checked)}
            disabled={isGenerating}
          />
          <span className={styles.checkboxLabel}>
            Оптимизировать промпт (ChatGPT 5.1)
          </span>
        </label>

        {/* Action Buttons */}
        <div className={styles.actionsRow}>
          <button
            className={styles.generateButton}
            onClick={handleGenerate}
            disabled={isGenerating || !userPrompt.trim()}
          >
            Сгенерировать
          </button>
          {showOptimized && !isGenerating && (
            <button
              className={styles.secondaryButton}
              onClick={handleGenerateDirect}
              disabled={!optimizedPrompt.trim()}
            >
              Перегенерировать с правками
            </button>
          )}
        </div>

        {/* Progress */}
        {isGenerating && progressMessage && (
          <div className={styles.progressSection}>
            <div className={styles.progressText}>
              <span className={styles.spinner} />
              {progressMessage}
            </div>
          </div>
        )}

        {/* Error */}
        {errorMessage && (
          <div className={styles.errorText}>{errorMessage}</div>
        )}

        {/* Optimized Prompt (editable) */}
        {showOptimized && (
          <div className={styles.optimizedSection}>
            <div className={styles.optimizedLabel}>
              Оптимизированный промпт (можно отредактировать):
            </div>
            <textarea
              className={styles.optimizedPrompt}
              value={optimizedPrompt}
              onChange={(e) => setOptimizedPrompt(e.target.value)}
              disabled={isGenerating}
            />
          </div>
        )}

        {/* Result */}
        {resultImagePath && (
          <div className={styles.resultSection}>
            <img
              src={`${API_BASE}/image-generator/image/${resultImagePath}`}
              alt="Результат генерации"
              className={styles.resultImage}
            />
            <div className={styles.resultActions}>
              <button
                className={styles.secondaryButton}
                onClick={() => handleDownload(resultImagePath)}
              >
                Скачать
              </button>
              <button
                className={styles.secondaryButton}
                onClick={() => startEditImage(resultImagePath)}
              >
                Редактировать
              </button>
              {resultCost !== null && (
                <span className={styles.costText}>
                  Стоимость: ${resultCost.toFixed(4)}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Edit Image Panel */}
      {editingImagePath && (
        <div className={styles.editSection}>
          <h2 className={styles.sectionTitle}>Редактирование изображения</h2>
          <div className={styles.editContent}>
            <img
              src={`${API_BASE}/image-generator/image/${editingImagePath}`}
              alt="Редактируемое изображение"
              className={styles.editPreviewImage}
            />
            <div className={styles.editForm}>
              <textarea
                className={styles.promptInput}
                value={editPrompt}
                onChange={(e) => setEditPrompt(e.target.value)}
                placeholder="Опишите какие правки нужно сделать..."
                disabled={isGenerating}
              />
              <div className={styles.actionsRow}>
                <button
                  className={styles.generateButton}
                  onClick={handleEditSubmit}
                  disabled={isGenerating || !editPrompt.trim()}
                >
                  Применить правки
                </button>
                <button
                  className={styles.secondaryButton}
                  onClick={cancelEdit}
                  disabled={isGenerating}
                >
                  Отмена
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* History Gallery */}
      <div className={styles.historySection}>
        <h2 className={styles.historyTitle}>История генераций</h2>

        {isLoading ? (
          <div className={styles.emptyState}>Загрузка...</div>
        ) : generations.length === 0 ? (
          <div className={styles.emptyState}>Нет сгенерированных изображений</div>
        ) : (
          <>
            <div className={styles.historyGrid}>
              {generations.map((gen) => (
                <div
                  key={gen.id}
                  className={styles.historyCard}
                  onClick={() => gen.image_path && setExpandedGen(gen)}
                >
                  {gen.image_path ? (
                    <img
                      src={`${API_BASE}/image-generator/image/${gen.image_path}`}
                      alt={gen.user_prompt}
                      className={styles.historyThumb}
                      loading="lazy"
                    />
                  ) : (
                    <div className={styles.historyThumb} style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 12, color: 'var(--text-tertiary)',
                    }}>
                      {gen.status === 'failed' ? 'Ошибка' : gen.status}
                    </div>
                  )}
                  <div className={styles.historyInfo}>
                    <span className={styles.historyPreset}>{getPresetLabel(gen.preset)}</span>
                    <p className={styles.historyPrompt}>{gen.user_prompt}</p>
                    <div className={styles.historyMeta}>
                      <span>{new Date(gen.created_at).toLocaleDateString('ru')}</span>
                      <span>${gen.cost_usd.toFixed(4)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {totalPages > 1 && (
              <div className={styles.pagination}>
                <button
                  className={styles.pageButton}
                  disabled={page === 0}
                  onClick={() => handlePageChange(page - 1)}
                >
                  Назад
                </button>
                <span style={{ fontSize: 13, color: 'var(--text-secondary)', alignSelf: 'center' }}>
                  {page + 1} / {totalPages}
                </span>
                <button
                  className={styles.pageButton}
                  disabled={page >= totalPages - 1}
                  onClick={() => handlePageChange(page + 1)}
                >
                  Далее
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Expanded Card Overlay */}
      {expandedGen && (
        <div className={styles.expandedOverlay} onClick={() => setExpandedGen(null)}>
          <div className={styles.expandedCard} onClick={(e) => e.stopPropagation()}>
            {expandedGen.image_path && (
              <img
                src={`${API_BASE}/image-generator/image/${expandedGen.image_path}`}
                alt={expandedGen.user_prompt}
                className={styles.expandedImage}
              />
            )}
            <div style={{ marginBottom: 8 }}>
              <span className={styles.historyPreset}>{getPresetLabel(expandedGen.preset)}</span>
            </div>
            <p className={styles.expandedPrompt}>
              <strong>Запрос:</strong> {expandedGen.user_prompt}
            </p>
            {expandedGen.optimized_prompt && (
              <p className={styles.expandedPrompt}>
                <strong>Оптимизированный промпт:</strong> {expandedGen.optimized_prompt}
              </p>
            )}
            <div className={styles.historyMeta} style={{ marginBottom: 16 }}>
              <span>{new Date(expandedGen.created_at).toLocaleString('ru')}</span>
              <span>Стоимость: ${expandedGen.cost_usd.toFixed(4)}</span>
            </div>
            <div className={styles.expandedActions}>
              {expandedGen.image_path && (
                <>
                  <button
                    className={styles.secondaryButton}
                    onClick={() => handleDownload(expandedGen.image_path!)}
                  >
                    Скачать
                  </button>
                  <button
                    className={styles.secondaryButton}
                    onClick={() => startEditImage(expandedGen.image_path!)}
                  >
                    Редактировать
                  </button>
                </>
              )}
              <button
                className={styles.deleteButton}
                onClick={() => handleDelete(expandedGen.id)}
              >
                Удалить
              </button>
              <button
                className={styles.secondaryButton}
                onClick={() => setExpandedGen(null)}
                style={{ marginLeft: 'auto' }}
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
