// Broadcast Form — создание / редактирование рассылки

import { useState, useCallback, useEffect } from 'react'
import { useBroadcastStore } from '@/store/broadcastStore'
import type { Broadcast, BroadcastButton, BroadcastTargetType } from '@/types'
import { RecipientSelector } from './RecipientSelector'
import { MessageEditor } from './MessageEditor'
import { PhotoUploader } from './PhotoUploader'
import { PollEditor } from './PollEditor'
import { ButtonEditor } from './ButtonEditor'
import styles from './BroadcastForm.module.css'

interface Props {
  broadcast: Broadcast | null
  onSaved: () => void
  onCancel: () => void
}

export function BroadcastForm({ broadcast, onSaved, onCancel }: Props) {
  const {
    createBroadcast,
    updateBroadcast,
    sendBroadcast,
    scheduleBroadcast,
    testSendBroadcast,
    isSending,
    isTestSending,
  } = useBroadcastStore()

  // Form fields
  const [title, setTitle] = useState(broadcast?.title || '')
  const [messageText, setMessageText] = useState(broadcast?.message_text || '')
  const [photoPath, setPhotoPath] = useState(broadcast?.photo_path || '')
  const [targetType, setTargetType] = useState<BroadcastTargetType>(broadcast?.target_type || 'all')
  const [targetInviteLinkId, setTargetInviteLinkId] = useState<number | null>(broadcast?.target_invite_link_id ?? null)
  const [targetFunnelId, setTargetFunnelId] = useState<string | null>(broadcast?.target_funnel_id ?? null)
  const [targetStageKey, setTargetStageKey] = useState<string | null>(broadcast?.target_stage_key ?? null)
  const [targetUserIds, setTargetUserIds] = useState<number[]>(broadcast?.target_user_ids || [])

  // Poll fields
  const [pollQuestion, setPollQuestion] = useState(broadcast?.poll_question || '')
  const [pollOptions, setPollOptions] = useState<string[]>(broadcast?.poll_options || ['', ''])
  const [pollAllowsMultiple, setPollAllowsMultiple] = useState(broadcast?.poll_allows_multiple ?? false)

  // Inline buttons
  const [inlineButtons, setInlineButtons] = useState<BroadcastButton[]>(broadcast?.inline_buttons || [])

  // Schedule
  const [scheduleEnabled, setScheduleEnabled] = useState(!!broadcast?.scheduled_at)
  const [scheduledAt, setScheduledAt] = useState(() => {
    if (broadcast?.scheduled_at) {
      return broadcast.scheduled_at.slice(0, 16) // yyyy-MM-ddTHH:mm
    }
    return ''
  })

  const [saving, setSaving] = useState(false)

  // Reset form when broadcast changes
  useEffect(() => {
    if (broadcast) {
      setTitle(broadcast.title || '')
      setMessageText(broadcast.message_text || '')
      setPhotoPath(broadcast.photo_path || '')
      setTargetType(broadcast.target_type || 'all')
      setTargetInviteLinkId(broadcast.target_invite_link_id ?? null)
      setTargetFunnelId(broadcast.target_funnel_id ?? null)
      setTargetStageKey(broadcast.target_stage_key ?? null)
      setTargetUserIds(broadcast.target_user_ids || [])
      setPollQuestion(broadcast.poll_question || '')
      setPollOptions(broadcast.poll_options || ['', ''])
      setPollAllowsMultiple(broadcast.poll_allows_multiple ?? false)
      setInlineButtons(broadcast.inline_buttons || [])
      setScheduleEnabled(!!broadcast.scheduled_at)
      setScheduledAt(broadcast.scheduled_at ? broadcast.scheduled_at.slice(0, 16) : '')
    }
  }, [broadcast])

  const buildDto = useCallback(() => {
    return {
      title: title.trim(),
      message_text: messageText.trim() || null,
      photo_path: photoPath || null,
      poll_question: pollQuestion.trim() || null,
      poll_options: pollQuestion.trim() ? pollOptions.filter((o) => o.trim()) : null,
      poll_is_anonymous: false,
      poll_allows_multiple: pollAllowsMultiple,
      inline_buttons: inlineButtons.length > 0 ? inlineButtons.filter((b) => b.text.trim()) : null,
      target_type: targetType,
      target_invite_link_id: targetType === 'invite_link' ? targetInviteLinkId : null,
      target_funnel_id: targetType === 'funnel_stage' ? targetFunnelId : null,
      target_stage_key: targetType === 'funnel_stage' ? targetStageKey : null,
      target_user_ids: targetType === 'manual' ? targetUserIds : null,
      scheduled_at: scheduleEnabled && scheduledAt ? scheduledAt : null,
    }
  }, [
    title, messageText, photoPath,
    pollQuestion, pollOptions, pollAllowsMultiple,
    inlineButtons,
    targetType, targetInviteLinkId, targetFunnelId, targetStageKey, targetUserIds,
    scheduleEnabled, scheduledAt,
  ])

  const hasContent = messageText.trim() || photoPath || pollQuestion.trim()
  const canSave = title.trim() && hasContent

  const handleSaveDraft = async () => {
    if (!canSave) return
    setSaving(true)
    const dto = buildDto()
    if (broadcast) {
      await updateBroadcast(broadcast.id, dto)
    } else {
      await createBroadcast(dto)
    }
    setSaving(false)
    onSaved()
  }

  const handleSendNow = async () => {
    if (!canSave) return
    setSaving(true)
    let id = broadcast?.id
    const dto = buildDto()
    if (id) {
      await updateBroadcast(id, dto)
    } else {
      const created = await createBroadcast(dto)
      id = created?.id
    }
    if (id) {
      await sendBroadcast(id)
    }
    setSaving(false)
    onSaved()
  }

  const handleSchedule = async () => {
    if (!canSave || !scheduledAt) return
    setSaving(true)
    let id = broadcast?.id
    const dto = buildDto()
    if (id) {
      await updateBroadcast(id, dto)
    } else {
      const created = await createBroadcast(dto)
      id = created?.id
    }
    if (id) {
      await scheduleBroadcast(id, scheduledAt)
    }
    setSaving(false)
    onSaved()
  }

  const handleTestSend = async () => {
    if (!canSave) return
    setSaving(true)
    let id = broadcast?.id
    const dto = buildDto()
    if (id) {
      await updateBroadcast(id, dto)
    } else {
      const created = await createBroadcast(dto)
      id = created?.id
    }
    if (id) {
      const success = await testSendBroadcast(id)
      if (success) {
        alert('Тестовое сообщение отправлено администраторам!')
      } else {
        alert('Ошибка при тестовой отправке')
      }
    }
    setSaving(false)
  }

  return (
    <div className={styles.form}>
      {/* Title */}
      <div className={styles.section}>
        <label className={styles.label}>Название рассылки</label>
        <input
          className={styles.input}
          type="text"
          placeholder="Например: Акция на февраль"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          autoFocus
        />
      </div>

      {/* Recipient Selector */}
      <div className={styles.section}>
        <label className={styles.label}>Получатели</label>
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

      {/* Message */}
      <div className={styles.section}>
        <label className={styles.label}>Сообщение</label>
        <MessageEditor
          value={messageText}
          onChange={setMessageText}
        />
      </div>

      {/* Photo */}
      <div className={styles.section}>
        <label className={styles.label}>Фото</label>
        <PhotoUploader
          photoPath={photoPath}
          onPhotoChange={setPhotoPath}
        />
      </div>

      {/* Poll */}
      <div className={styles.section}>
        <PollEditor
          pollQuestion={pollQuestion}
          pollOptions={pollOptions}
          pollAllowsMultiple={pollAllowsMultiple}
          onChange={({ question, options, allowsMultiple }) => {
            if (question !== undefined) setPollQuestion(question)
            if (options !== undefined) setPollOptions(options)
            if (allowsMultiple !== undefined) setPollAllowsMultiple(allowsMultiple)
          }}
        />
      </div>

      {/* Inline Buttons */}
      <div className={styles.section}>
        <ButtonEditor
          buttons={inlineButtons}
          onChange={setInlineButtons}
        />
      </div>

      {/* Schedule */}
      <div className={styles.section}>
        <div className={styles.scheduleToggle}>
          <label className={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={scheduleEnabled}
              onChange={(e) => setScheduleEnabled(e.target.checked)}
            />
            <span>Запланировать отправку</span>
          </label>
        </div>
        {scheduleEnabled && (
          <input
            className={styles.input}
            type="datetime-local"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            min={new Date().toISOString().slice(0, 16)}
          />
        )}
      </div>

      {/* Actions */}
      <div className={styles.actions}>
        <button
          className={styles.testButton}
          onClick={handleTestSend}
          disabled={!canSave || saving || isSending || isTestSending}
        >
          {isTestSending ? 'Отправка...' : 'Проверить'}
        </button>

        <button
          className={styles.draftButton}
          onClick={handleSaveDraft}
          disabled={!canSave || saving || isSending}
        >
          {saving ? 'Сохранение...' : 'Сохранить черновик'}
        </button>

        {scheduleEnabled ? (
          <button
            className={styles.scheduleButton}
            onClick={handleSchedule}
            disabled={!canSave || !scheduledAt || saving || isSending}
          >
            Запланировать
          </button>
        ) : (
          <button
            className={styles.sendButton}
            onClick={handleSendNow}
            disabled={!canSave || saving || isSending}
          >
            {isSending ? 'Отправка...' : 'Отправить сейчас'}
          </button>
        )}

        <button className={styles.cancelButton} onClick={onCancel}>
          Отмена
        </button>
      </div>
    </div>
  )
}
