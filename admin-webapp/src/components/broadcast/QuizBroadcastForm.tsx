// Quiz Broadcast Form — упрощённая форма рассылки квиза существующим пользователям

import { useState, useCallback } from 'react'
import { useBroadcastStore } from '@/store/broadcastStore'
import type { BroadcastTargetType } from '@/types'
import { RecipientSelector } from './RecipientSelector'
import styles from './QuizBroadcastForm.module.css'

const QUIZ_TEXT = `Я - PRO Растения, агроном в Telegram.

Ухаживать за растениями очень просто! Но на практике можно терять 20-40% урожая из-за маленького пробела в уходе.

Я помогу разобраться! Уделите 30 секунд - мы сделаем диагностику и дам я практические рекомендации!

Нажмите START - 1 чат вместо 1000 книг!`

const QUIZ_HTML = QUIZ_TEXT
  .split('\n\n')
  .map(p => `<p>${p}</p>`)
  .join('')

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
      inline_buttons: [{ row: 0, text: 'START', type: 'quiz_start', option_key: 'quiz_start' }],
      poll_question: null,
      poll_options: null,
      poll_allows_multiple: false,
      reminders: [],
    })

    if (broadcast) {
      await testSendBroadcast(broadcast.id)
    }
  }, [createBroadcast, testSendBroadcast, targetType, targetInviteLinkId, targetFunnelId, targetStageKey, targetUserIds])

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
      inline_buttons: [{ row: 0, text: 'START', type: 'quiz_start', option_key: 'quiz_start' }],
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
  }, [createBroadcast, sendBroadcast, targetType, targetInviteLinkId, targetFunnelId, targetStageKey, targetUserIds, recipientPreviewCount])

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
        </div>
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
