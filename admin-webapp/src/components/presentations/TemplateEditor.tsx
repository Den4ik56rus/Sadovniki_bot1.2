// Template Editor — modal for managing presentation structure templates
import { useState } from 'react'
import { api } from '@/services/api'
import type { PresentationTemplate } from '@/types'
import css from './PresentationsPage.module.css'

interface Props {
  templates: PresentationTemplate[]
  onClose: () => void
}

const TEMPLATE_PRESETS: Record<string, { name: string; description: string; text: string }> = {
  diagnosis_plan: {
    name: 'Диагностика + План',
    description: '15 слайдов: диагноз, план по фазам, контроль, системное мышление',
    text: `🟢 БЛОК 1 — Диагноз и ориентация (1–3 слайды)

Слайд 1 — Заголовок
[Культура] — [Проблема]
Как исправить ситуацию без потери урожая
Подзаголовок: Пошаговый план по фазам роста

Слайд 2 — Что на самом деле происходит
Что вы наблюдаете
В какой фазе чаще формируется проблема
Сколько урожая обычно теряется
Главный фактор риска
(4–5 коротких пунктов)

Слайд 3 — Определите свою фазу
Список фаз, релевантных проблеме:
🌱 Рост листа
🌸 Цветение
🍓 Завязь
🍒 Налив
✂ После сбора
1 строка пояснения, как понять, где вы сейчас.

🟡 БЛОК 2 — План по фазам (4–11 слайды)
Обычно 3 фазы × 2 слайда каждая.

Для каждой фазы — 2 слайда:

Слайд X — Фаза: [Название]
Что сделать сейчас:
Конкретное действие
Норма (граммы, литры, частота)
Что проверить
Что убрать
Максимум 5 пунктов.

Слайд X+1 — Ошибки в этой фазе
Чего нельзя делать:
Ошибка 1
Ошибка 2
Ошибка 3
Что подготовить к следующей фазе
2–3 пункта.

🔵 БЛОК 3 — Контроль результата (12–13 слайды)

Слайд 12 — Когда ждать результат
Через сколько дней будут первые изменения
Какие признаки улучшения
Как понять, что всё идёт правильно

Слайд 13 — Если улучшений нет
Что проверить
Когда корректировать
В каких случаях нужна системная корректировка

🔴 БЛОК 4 — Системное мышление (14–15 слайды)

Слайд 14 — 5 критических ошибок сезона
Ошибка 1
Ошибка 2
Ошибка 3
Ошибка 4
Ошибка 5
(То, что возвращает проблему снова)

Слайд 15 — Важный момент
Мягкий мост к флагману:
Вы сейчас устраняете конкретную проблему.
Но урожай формируется всей системой: питание + полив + защита + обрезка.
Если одна фаза провалена — результат нестабилен.
Без агрессивной продажи. Просто логичный вывод.`,
  },
  botanical_blueprint: {
    name: 'Botanical Blueprint',
    description: '15 слайдов с типами layout для стиля Botanical Blueprint',
    text: `🟢 БЛОК 1 — Диагностика (слайды 1–3)

Слайд 1 — ТИТУЛЬНЫЙ (layout: title_slide)
Заголовок: [Культура]: [Схема/Проблема]
Подзаголовок: Как избежать [проблема] и [потери]
Формат: сравнение "неправильно vs правильно" — слева хаотичная/неправильная картина (красные тона), справа аккуратная/правильная (зелёные тона).
Подпись: Пошаговый план по фазам роста

Слайд 2 — Что на самом деле происходит (layout: content_slide)
Большая детальная иллюстрация проблемы (например: загущенная посадка, больное растение, разрез почвы с проблемами).
Иллюстрация слева с увеличительным стеклом / лупой на ключевом месте проблемы.
Справа — текстовые пункты:
• Наблюдение: что видно
• Фаза риска: когда формируется
• Потери: сколько теряется (%)
• Главный фактор: причина
• Итог: к чему приводит

Слайд 3 — Определите свою фазу (layout: process_slide)
3 фазы роста в кружках с иллюстрациями, соединёнными стрелками слева направо.
Каждый кружок: иллюстрация стадии + подпись под кружком (название фазы + 1 строка описания).
Примечание внизу: "Если вы уже [сделали X] — переходите к Блоку 3."

🟡 БЛОК 2 — План по фазам (слайды 4–11)
Для каждой фазы — 2 слайда (обычно 3-4 фазы × 2 слайда).

Слайд X — Фаза: [Название] (layout: content_slide или measurements_slide)
Заголовок: "ФАЗА: [НАЗВАНИЕ]"
Подзаголовок: "Что сделать сейчас"
Большая иллюстрация — ботаническая, с размерными линиями и стрелками если применимо.
Текстовые пункты (max 5):
• Действие: конкретное действие с нормами
• Питание/Полив: точные нормы (граммы/литры)
• Проверка: что убедиться
• Защита: если нужно
• Чек-лист: ключевой критерий успеха

Слайд X+1 — Ошибки [название фазы] (layout: mistakes_slide)
Заголовок: "ОШИБКИ [ФАЗЫ]" (красный)
Подзаголовок: "Чего нельзя делать"
2-3 иллюстрации типичных ошибок с красными X поверх.
Под каждой иллюстрацией — текст ошибки (1 строка).
Внизу подпись: что подготовить к следующей фазе.

🔵 БЛОК 3 — Контроль результата (слайды 12–13)

Слайд 12 — Когда ждать результат (layout: results_slide)
Заголовок: "КОГДА ЖДАТЬ РЕЗУЛЬТАТ"
Подзаголовок: "Признаки успеха"
Иллюстрация здорового/успешного результата (зелёные тона, красивые ровные ряды).
Зелёная галочка.
Пункты:
• Сроки: через сколько видны изменения
• Визуально: что должно быть видно
• Рост: как ведут себя растения
• Доступ: что можно делать

Слайд 13 — Если улучшений нет (layout: content_slide)
Заголовок: "ЕСЛИ УЛУЧШЕНИЙ НЕТ"
Подзаголовок: "Корректировка"
Иллюстрация: растение с лопатой (пересадка/коррекция).
Пункты:
• Проблема: что вы наблюдаете
• Решение 1: мягкая корректировка
• Решение 2: средняя корректировка
• Радикально: если место/условия неподходящие

🔴 БЛОК 4 — Системное мышление (слайды 14–15)

Слайд 14 — Критические ошибки сезона (layout: content_slide)
Заголовок: "5 КРИТИЧЕСКИХ ОШИБОК СЕЗОНА"
Подзаголовок: "То, что возвращает проблему"
Крупные красные номера 1-5 слева.
Текст каждой ошибки справа от номера.
Маленькие иллюстрации к каждой ошибке справа.
Декоративная рамка (колонны/арка) вокруг контента.

Слайд 15 — Важный момент (layout: summary_slide)
Заголовок: "ВАЖНЫЙ МОМЕНТ"
Подзаголовок: "Системный подход"
Архитектурная метафора: храм/здание нарисованное пером.
Фундамент = базовая практика (геометрия, расстояния).
Колонны = ключевые практики (питание, защита, обрезка).
Крыша/фронтон = УРОЖАЙ.
Текст: "Правильная схема — это фундамент. Но урожай формируется всей системой."
Красный акцент на одной колонне: "Если одна фаза провалена — результат нестабилен."`,
  },
}

const DEFAULT_TEMPLATE_TEXT = TEMPLATE_PRESETS.diagnosis_plan.text

export function TemplateEditor({ templates: templatesList, onClose }: Props) {
  const [editingId, setEditingId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [templateText, setTemplateText] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleNew = () => {
    setEditingId(null)
    setName('')
    setDescription('')
    setTemplateText(DEFAULT_TEMPLATE_TEXT)
  }

  const handleLoadPreset = (presetKey: string) => {
    const preset = TEMPLATE_PRESETS[presetKey]
    if (!preset) return
    setName(preset.name)
    setDescription(preset.description)
    setTemplateText(preset.text)
  }

  const handleEdit = (template: PresentationTemplate) => {
    setEditingId(template.id)
    setName(template.name)
    setDescription(template.description || '')
    setTemplateText(template.template_text)
  }

  const handleSave = async () => {
    if (!name.trim() || !templateText.trim()) return
    setIsSaving(true)
    setError(null)

    try {
      if (editingId) {
        await api.updatePresentationTemplate(editingId, {
          name: name.trim(),
          description: description.trim() || undefined,
          template_text: templateText.trim(),
        })
      } else {
        await api.createPresentationTemplate({
          name: name.trim(),
          description: description.trim() || undefined,
          template_text: templateText.trim(),
        })
      }
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка сохранения')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить шаблон?')) return
    try {
      await api.deletePresentationTemplate(id)
      onClose()
    } catch (err) {
      console.error('Failed to delete template:', err)
    }
  }

  // Count slides in template text
  const slideCount = (templateText.match(/Слайд\s+\d+|Слайд\s+X/gi) || []).length

  return (
    <div className={css.modalOverlay} onClick={onClose}>
      <div className={css.modalContent} onClick={e => e.stopPropagation()}>
        <div className={css.modalHeader}>
          <h3>Шаблоны структуры</h3>
          <button className={css.modalClose} onClick={onClose}>&times;</button>
        </div>

        <div className={css.styleEditorLayout}>
          {/* Left: list of templates */}
          <div className={css.styleList}>
            <button className={css.styleListAdd} onClick={handleNew}>
              + Новый шаблон
            </button>
            {templatesList.map(t => (
              <div
                key={t.id}
                className={`${css.styleListItem} ${editingId === t.id ? css.styleListItemActive : ''}`}
              >
                <button className={css.styleListName} onClick={() => handleEdit(t)}>
                  {t.name}
                </button>
                <button className={css.styleListDelete} onClick={() => handleDelete(t.id)}>
                  &times;
                </button>
              </div>
            ))}
            {templatesList.length === 0 && (
              <div className={css.empty}>Шаблонов нет</div>
            )}
          </div>

          {/* Right: editor */}
          <div className={css.styleForm}>
            {/* Presets */}
            <div className={css.field}>
              <label className={css.label}>Загрузить пресет</label>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {Object.entries(TEMPLATE_PRESETS).map(([key, preset]) => (
                  <button
                    key={key}
                    className={css.styleListAdd}
                    onClick={() => handleLoadPreset(key)}
                    title={preset.description}
                    style={{ fontSize: '12px', padding: '4px 10px' }}
                  >
                    {preset.name}
                  </button>
                ))}
              </div>
            </div>

            <div className={css.field}>
              <label className={css.label}>Название</label>
              <input
                className={css.textInput}
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="Диагностика + план действий"
              />
            </div>

            <div className={css.field}>
              <label className={css.label}>Описание</label>
              <input
                className={css.textInput}
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="15 слайдов: диагноз, план по фазам, контроль, системное мышление"
              />
            </div>

            <div className={css.field}>
              <label className={css.label}>
                Текст шаблона
                {slideCount > 0 && (
                  <span className={css.count}>{slideCount} слайдов</span>
                )}
              </label>
              <textarea
                className={css.textarea}
                value={templateText}
                onChange={e => setTemplateText(e.target.value)}
                rows={20}
                placeholder="Опишите структуру презентации: блоки, слайды, что должно быть на каждом..."
              />
            </div>

            {error && <div className={css.error}>{error}</div>}

            <button
              className={css.generateButton}
              onClick={handleSave}
              disabled={isSaving || !name.trim() || !templateText.trim()}
            >
              {isSaving ? 'Сохранение...' : editingId ? 'Обновить' : 'Создать'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
