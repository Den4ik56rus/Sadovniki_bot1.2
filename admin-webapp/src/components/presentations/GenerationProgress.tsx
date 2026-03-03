// Generation Progress — SSE-driven progress display with live slide preview
import { api } from '@/services/api'
import type { PresentationProgressEvent, CompletedSlideInfo } from '@/types'
import styles from './PresentationsPage.module.css'

interface Props {
  progress: PresentationProgressEvent | null
  completedSlides?: CompletedSlideInfo[]
}

export function GenerationProgress({ progress, completedSlides = [] }: Props) {
  if (!progress) {
    return (
      <div className={styles.progressContainer}>
        <div className={styles.progressBar}>
          <div className={styles.progressFill} style={{ width: '0%' }} />
        </div>
        <p className={styles.progressText}>Подготовка...</p>
      </div>
    )
  }

  const { type, slide_index, slide_count, slide_title, total_image_cost_usd, text_cost_usd, total_cost_usd, message, error } = progress

  let progressPercent = 0
  let statusText = ''

  switch (type) {
    case 'generation_started':
      statusText = 'Генерация началась...'
      progressPercent = 2
      break
    case 'article_generating':
      statusText = message || 'Генерация статьи по проблеме...'
      progressPercent = 3
      break
    case 'article_completed':
      statusText = `Статья сгенерирована (${((progress.article_length ?? 0) / 1000).toFixed(1)}K символов). Стоимость: $${(progress.article_cost_usd ?? 0).toFixed(4)}`
      progressPercent = 8
      break
    case 'text_processing':
      statusText = message || 'GPT обрабатывает текст...'
      progressPercent = 10
      break
    case 'slides_planned':
      statusText = `GPT создал ${slide_count} слайдов. Стоимость текста: $${(text_cost_usd ?? 0).toFixed(4)}`
      progressPercent = 15
      break
    case 'slide_generating':
      statusText = `Генерация слайда ${(slide_index ?? 0) + 1} из ${slide_count}: ${slide_title || ''}`
      progressPercent = slide_count ? 15 + ((slide_index ?? 0) / slide_count) * 80 : 50
      break
    case 'slide_completed':
      statusText = `Слайд ${(slide_index ?? 0) + 1} из ${slide_count} готов. Стоимость: $${(total_image_cost_usd ?? 0).toFixed(4)}`
      progressPercent = slide_count ? 15 + (((slide_index ?? 0) + 1) / slide_count) * 80 : 50
      break
    case 'slide_failed':
      statusText = `Ошибка слайда ${(slide_index ?? 0) + 1}: ${error}`
      progressPercent = slide_count ? 15 + (((slide_index ?? 0) + 1) / slide_count) * 80 : 50
      break
    case 'building_pdf':
      statusText = 'Сборка PDF...'
      progressPercent = 95
      break
    case 'generation_completed':
      statusText = `Готово! ${slide_count} слайдов, итого: $${(total_cost_usd ?? 0).toFixed(4)}`
      progressPercent = 100
      break
    case 'generation_failed':
      statusText = `Ошибка: ${error}`
      progressPercent = 100
      break
    default:
      statusText = message || type || 'Обработка...'
      progressPercent = 50
  }

  // Build placeholder slots for slides not yet completed
  const totalSlots = slide_count ?? 0
  const slots: Array<CompletedSlideInfo | null> = []
  for (let i = 0; i < totalSlots; i++) {
    const completed = completedSlides.find(s => s.slide_index === i)
    slots.push(completed ?? null)
  }

  return (
    <div className={styles.progressContainer}>
      {/* Progress bar + counter */}
      <div className={styles.progressHeader}>
        <div className={styles.progressBar}>
          <div
            className={`${styles.progressFill} ${type === 'generation_failed' ? styles.progressFillError : ''} ${type === 'generation_completed' ? styles.progressFillDone : ''}`}
            style={{ width: `${Math.min(progressPercent, 100)}%` }}
          />
        </div>
        {totalSlots > 0 && (
          <span className={styles.progressCounter}>
            {completedSlides.length}/{totalSlots}
          </span>
        )}
      </div>
      <p className={styles.progressText}>{statusText}</p>

      {/* Live slide preview grid */}
      {totalSlots > 0 && (
        <div className={styles.livePreviewGrid}>
          {slots.map((slot, i) => (
            <div key={i} className={styles.livePreviewCard}>
              {slot ? (
                <img
                  className={styles.livePreviewThumb}
                  src={api.getSlideImageUrl(slot.version_id)}
                  alt={slot.slide_title || `Слайд ${i + 1}`}
                />
              ) : (
                <div className={`${styles.livePreviewPlaceholder} ${
                  slide_index !== undefined && i === slide_index && type === 'slide_generating'
                    ? styles.livePreviewGenerating
                    : ''
                }`}>
                  {slide_index !== undefined && i === slide_index && type === 'slide_generating' ? (
                    <span className={styles.spinner} />
                  ) : (
                    <span className={styles.livePreviewIndex}>{i + 1}</span>
                  )}
                </div>
              )}
              <div className={styles.livePreviewLabel}>
                <span className={styles.livePreviewNum}>{i + 1}</span>
                {slot && <span className={styles.livePreviewTitle}>{slot.slide_title}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
