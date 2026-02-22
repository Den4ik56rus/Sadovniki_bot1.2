// Resend Dialog — диалог повторной отправки рассылки

import { useState } from 'react'
import { useBroadcastStore } from '@/store/broadcastStore'
import type { BroadcastTargetType } from '@/types'
import { RecipientSelector } from './RecipientSelector'
import styles from './ResendDialog.module.css'

interface Props {
  broadcastId: number
  onClose: () => void
}

export function ResendDialog({ broadcastId, onClose }: Props) {
  const { resendBroadcast, isSending } = useBroadcastStore()

  const [targetType, setTargetType] = useState<BroadcastTargetType>('all')
  const [targetInviteLinkId, setTargetInviteLinkId] = useState<number | null>(null)
  const [targetFunnelId, setTargetFunnelId] = useState<string | null>(null)
  const [targetStageKey, setTargetStageKey] = useState<string | null>(null)
  const [targetUserIds, setTargetUserIds] = useState<number[]>([])

  const handleSend = async () => {
    if (!confirm('Повторить рассылку выбранным получателям?')) return
    const ok = await resendBroadcast(broadcastId, {
      target_type: targetType,
      target_invite_link_id: targetType === 'invite_link' ? targetInviteLinkId : null,
      target_funnel_id: targetType === 'funnel_stage' ? targetFunnelId : null,
      target_stage_key: targetType === 'funnel_stage' ? targetStageKey : null,
      target_user_ids: targetType === 'manual' ? targetUserIds : null,
    })
    if (ok) onClose()
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h3 className={styles.title}>Повторить рассылку</h3>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div className={styles.body}>
          <p className={styles.hint}>
            Выберите новую аудиторию для повторной отправки.
            Сообщение останется прежним, но статистика будет отдельной.
          </p>

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

        <div className={styles.footer}>
          <button className={styles.cancelBtn} onClick={onClose} disabled={isSending}>
            Отмена
          </button>
          <button className={styles.sendBtn} onClick={handleSend} disabled={isSending}>
            {isSending ? 'Отправка...' : 'Отправить'}
          </button>
        </div>
      </div>
    </div>
  )
}
