// Quiz Broadcast Form — упрощённая форма рассылки квиза существующим пользователям

import { useState, useCallback, useEffect } from 'react'
import { useBroadcastStore } from '@/store/broadcastStore'
import type { BroadcastTargetType, BroadcastButton } from '@/types'
import { RecipientSelector } from './RecipientSelector'
import styles from './QuizBroadcastForm.module.css'

const API = import.meta.env.VITE_API_URL || ''

const QUIZ_TEXT = `Я - PRO Растения, агроном в Telegram.

Ухаживать за растениями очень просто! Но на практике можно терять 20-40% урожая из-за маленького пробела в уходе.

Я помогу разобраться! Уделите 30 секунд - мы сделаем диагностику и дам я практические рекомендации!

Нажмите START - 1 чат вместо 1000 книг!`

const QUIZ_HTML = QUIZ_TEXT
  .split('\n\n')
  .map(p => `<p>${p}</p>`)
  .join('')

interface Tag {
  id: number
  name: string
  color: string
}

export function QuizBroadcastForm() {
  const {
    createBroadcast,
    sendBroadcast,
    testSendBroadcast,
    recipientPreviewCount,
    isSending,
    isTestSending,
  } = useBroadcastStore()

  const [targetType, setTargetType] = useState<BroadcastTargetType>('all')
  const [targetInviteLinkId, setTargetInviteLinkId] = useState<number | null>(null)
  const [targetFunnelId, setTargetFunnelId] = useState<string | null>(null)
  const [targetStageKey, setTargetStageKey] = useState<string | null>(null)
  const [targetUserIds, setTargetUserIds] = useState<number[]>([])
  const [sending, setSending] = useState(false)
  const [sentResult, setSentResult] = useState<string | null>(null)

  // Динамическая цена
  const [quizPrice, setQuizPrice] = useState<number>(99)
  const [quizOriginalPrice, setQuizOriginalPrice] = useState<number>(490)

  // Авто-тег
  const [quizTagId, setQuizTagId] = useState<number | null>(null)
  const [tags, setTags] = useState<Tag[]>([])
  const [showNewTag, setShowNewTag] = useState(false)
  const [newTagName, setNewTagName] = useState('')
  const [newTagColor, setNewTagColor] = useState('#4A7C59')

  // Загрузка тегов
  useEffect(() => {
    fetch(`${API}/api/admin/crm/tags`)
      .then(r => r.json())
      .then(data => setTags(Array.isArray(data) ? data : (data.tags || [])))
      .catch(() => {})
  }, [])

  const handleCreateTag = useCallback(async () => {
    if (!newTagName.trim()) return
    try {
      const res = await fetch(`${API}/api/admin/crm/tags`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newTagName.trim(), color: newTagColor }),
      })
      const data = await res.json()
      // API returns tag object directly (or {tag: ...})
      const tag = data.tag || data
      if (tag && tag.id) {
        setTags(prev => [...prev, tag])
        setQuizTagId(tag.id)
        setNewTagName('')
        setShowNewTag(false)
      }
    } catch {}
  }, [newTagName, newTagColor])

  const buildInlineButtons = useCallback((): BroadcastButton[] => {
    const btn: BroadcastButton = {
      row: 0,
      text: 'START',
      type: 'quiz_start',
      option_key: 'quiz_start',
      quiz_price: quizPrice,
      quiz_original_price: quizOriginalPrice,
      quiz_tag_id: quizTagId,
    }
    return [btn]
  }, [quizPrice, quizOriginalPrice, quizTagId])

  const handleTestSend = useCallback(async () => {
    const now = new Date()
    const title = `Квиз-рассылка (тест) ${now.toLocaleDateString('ru')}`

    const broadcast = await createBroadcast({
      title,
      message_text: QUIZ_HTML,
      photo_path: null,
      target_type: targetType,
      target_invite_link_id: targetType === 'invite_link' ? targetInviteLinkId : null,
      target_funnel_id: targetType === 'funnel_stage' ? targetFunnelId : null,
      target_stage_key: targetType === 'funnel_stage' ? targetStageKey : null,
      target_user_ids: targetType === 'manual' ? targetUserIds : null,
      inline_buttons: buildInlineButtons(),
      poll_question: null,
      poll_options: null,
      poll_allows_multiple: false,
      reminders: [],
    })

    if (broadcast) {
      await testSendBroadcast(broadcast.id)
    }
  }, [createBroadcast, testSendBroadcast, targetType, targetInviteLinkId, targetFunnelId, targetStageKey, targetUserIds, buildInlineButtons])

  const handleSend = useCallback(async () => {
    const count = recipientPreviewCount ?? 0
    if (count === 0) return
    if (!confirm(`Отправить квиз-рассылку ${count} получателям?`)) return

    setSending(true)
    setSentResult(null)

    const now = new Date()
    const title = `Квиз-рассылка ${now.toLocaleDateString('ru')}`

    const broadcast = await createBroadcast({
      title,
      message_text: QUIZ_HTML,
      photo_path: null,
      target_type: targetType,
      target_invite_link_id: targetType === 'invite_link' ? targetInviteLinkId : null,
      target_funnel_id: targetType === 'funnel_stage' ? targetFunnelId : null,
      target_stage_key: targetType === 'funnel_stage' ? targetStageKey : null,
      target_user_ids: targetType === 'manual' ? targetUserIds : null,
      inline_buttons: buildInlineButtons(),
      poll_question: null,
      poll_options: null,
      poll_allows_multiple: false,
      reminders: [],
    })

    if (broadcast) {
      const ok = await sendBroadcast(broadcast.id)
      setSentResult(ok ? 'success' : 'error')
    } else {
      setSentResult('error')
    }
    setSending(false)
  }, [createBroadcast, sendBroadcast, targetType, targetInviteLinkId, targetFunnelId, targetStageKey, targetUserIds, recipientPreviewCount, buildInlineButtons])

  // Превью цены
  const pricePreview = quizPrice === 0
    ? `Обычно стоит ${quizOriginalPrice} ₽ → Бесплатно`
    : `${quizOriginalPrice} ₽ → ${quizPrice} ₽`

  return (
    <div className={styles.form}>
      {/* Превью сообщения */}
      <div className={styles.section}>
        <div className={styles.label}>Сообщение</div>
        <div className={styles.messagePreview}>
          {QUIZ_TEXT.split('\n\n').map((paragraph, i) => (
            <p key={i}>{paragraph}</p>
          ))}
          <div className={styles.buttonPreview}>START</div>
          <div className={styles.pricePreview}>{pricePreview}</div>
        </div>
      </div>

      {/* Цена */}
      <div className={styles.section}>
        <div className={styles.label}>Цена квиз-плана</div>
        <div className={styles.priceRow}>
          <div className={styles.priceField}>
            <label className={styles.priceLabel}>Цена (0 = бесплатно)</label>
            <input
              type="number"
              min={0}
              value={quizPrice}
              onChange={e => setQuizPrice(Number(e.target.value))}
              className={styles.priceInput}
            />
          </div>
          <div className={styles.priceField}>
            <label className={styles.priceLabel}>Оригинальная (зачёркнутая)</label>
            <input
              type="number"
              min={0}
              value={quizOriginalPrice}
              onChange={e => setQuizOriginalPrice(Number(e.target.value))}
              className={styles.priceInput}
            />
          </div>
        </div>
      </div>

      {/* Тег */}
      <div className={styles.section}>
        <div className={styles.label}>Авто-тег (необязательно)</div>
        <div className={styles.tagRow}>
          <select
            value={quizTagId ?? ''}
            onChange={e => setQuizTagId(e.target.value ? Number(e.target.value) : null)}
            className={styles.tagSelect}
          >
            <option value="">Без тега</option>
            {tags.map(t => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
          <button
            type="button"
            className={styles.newTagButton}
            onClick={() => setShowNewTag(!showNewTag)}
          >
            {showNewTag ? 'Отмена' : '+ Новый тег'}
          </button>
        </div>
        {showNewTag && (
          <div className={styles.newTagForm}>
            <input
              type="text"
              placeholder="Название тега"
              value={newTagName}
              onChange={e => setNewTagName(e.target.value)}
              className={styles.priceInput}
            />
            <input
              type="color"
              value={newTagColor}
              onChange={e => setNewTagColor(e.target.value)}
              className={styles.colorInput}
            />
            <button
              type="button"
              className={styles.testButton}
              onClick={handleCreateTag}
              disabled={!newTagName.trim()}
            >
              Создать
            </button>
          </div>
        )}
      </div>

      {/* Получатели */}
      <div className={styles.section}>
        <div className={styles.label}>Получатели</div>
        <RecipientSelector
          targetType={targetType}
          onTargetTypeChange={setTargetType}
          targetInviteLinkId={targetInviteLinkId}
          onInviteLinkChange={setTargetInviteLinkId}
          targetFunnelId={targetFunnelId}
          onFunnelChange={setTargetFunnelId}
          targetStageKey={targetStageKey}
          onStageChange={setTargetStageKey}
          targetUserIds={targetUserIds}
          onUserIdsChange={setTargetUserIds}
        />
      </div>

      {/* Результат отправки */}
      {sentResult === 'success' && (
        <div className={styles.successBanner}>
          Квиз-рассылка отправлена!
        </div>
      )}
      {sentResult === 'error' && (
        <div className={styles.errorBanner}>
          Ошибка при отправке рассылки
        </div>
      )}

      {/* Действия */}
      <div className={styles.actions}>
        <button
          className={styles.testButton}
          onClick={handleTestSend}
          disabled={isTestSending || sending}
        >
          {isTestSending ? 'Отправка...' : 'Тест (себе)'}
        </button>
        <button
          className={styles.sendButton}
          onClick={handleSend}
          disabled={isSending || sending || (recipientPreviewCount ?? 0) === 0}
        >
          {sending ? 'Отправка...' : `Отправить${recipientPreviewCount ? ` (${recipientPreviewCount})` : ''}`}
        </button>
      </div>
    </div>
  )
}
