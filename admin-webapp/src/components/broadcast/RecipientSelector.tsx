// Recipient Selector — выбор целевой аудитории рассылки

import { useEffect, useState, useCallback } from 'react'
import { useBroadcastStore } from '@/store/broadcastStore'
import { api } from '@/services/api'
import type { BroadcastTargetType, InviteLink, Funnel, FunnelStage } from '@/types'
import { ManualUserPicker } from './ManualUserPicker'
import styles from './RecipientSelector.module.css'

const TABS: { key: BroadcastTargetType; label: string }[] = [
  { key: 'all', label: 'Все пользователи' },
  { key: 'invite_link', label: 'По инвайт-ссылке' },
  { key: 'funnel_stage', label: 'По воронке' },
  { key: 'manual', label: 'Вручную' },
]

interface Props {
  targetType: BroadcastTargetType
  onTargetTypeChange: (t: BroadcastTargetType) => void
  targetInviteLinkId: number | null
  onInviteLinkChange: (id: number | null) => void
  targetFunnelId: string | null
  onFunnelChange: (id: string | null) => void
  targetStageKey: string | null
  onStageChange: (key: string | null) => void
  targetUserIds: number[]
  onUserIdsChange: (ids: number[]) => void
}

export function RecipientSelector({
  targetType,
  onTargetTypeChange,
  targetInviteLinkId,
  onInviteLinkChange,
  targetFunnelId,
  onFunnelChange,
  targetStageKey,
  onStageChange,
  targetUserIds,
  onUserIdsChange,
}: Props) {
  const { recipientPreviewCount, previewCount } = useBroadcastStore()

  const [inviteLinks, setInviteLinks] = useState<InviteLink[]>([])
  const [funnels, setFunnels] = useState<Funnel[]>([])
  const [stages, setStages] = useState<FunnelStage[]>([])
  const [loadingLinks, setLoadingLinks] = useState(false)
  const [loadingFunnels, setLoadingFunnels] = useState(false)
  const [loadingStages, setLoadingStages] = useState(false)

  // Load invite links when tab is selected
  useEffect(() => {
    if (targetType === 'invite_link' && inviteLinks.length === 0) {
      setLoadingLinks(true)
      api.getInviteLinks().then((data) => {
        setInviteLinks(data.links)
      }).catch(() => {}).finally(() => setLoadingLinks(false))
    }
  }, [targetType, inviteLinks.length])

  // Load funnels when tab is selected
  useEffect(() => {
    if (targetType === 'funnel_stage' && funnels.length === 0) {
      setLoadingFunnels(true)
      api.getFunnels().then((data) => {
        setFunnels(data.funnels)
      }).catch(() => {}).finally(() => setLoadingFunnels(false))
    }
  }, [targetType, funnels.length])

  // Load stages when funnel is selected
  useEffect(() => {
    if (targetFunnelId) {
      setLoadingStages(true)
      setStages([])
      onStageChange(null)
      api.getFunnelStages(targetFunnelId).then((data) => {
        setStages(data.stages)
      }).catch(() => {}).finally(() => setLoadingStages(false))
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetFunnelId])

  // Preview count when target params change
  const updatePreviewCount = useCallback(() => {
    previewCount({
      target_type: targetType,
      target_invite_link_id: targetType === 'invite_link' ? targetInviteLinkId : null,
      target_funnel_id: targetType === 'funnel_stage' ? targetFunnelId : null,
      target_stage_key: targetType === 'funnel_stage' ? targetStageKey : null,
      target_user_ids: targetType === 'manual' ? targetUserIds : null,
    })
  }, [targetType, targetInviteLinkId, targetFunnelId, targetStageKey, targetUserIds, previewCount])

  useEffect(() => {
    updatePreviewCount()
  }, [updatePreviewCount])

  const handleTabChange = (key: BroadcastTargetType) => {
    onTargetTypeChange(key)
  }

  return (
    <div className={styles.container}>
      {/* Tabs */}
      <div className={styles.tabs}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`${styles.tab} ${targetType === tab.key ? styles.tabActive : ''}`}
            onClick={() => handleTabChange(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className={styles.tabContent}>
        {targetType === 'all' && (
          <div className={styles.infoText}>
            Рассылка будет отправлена всем пользователям бота.
          </div>
        )}

        {targetType === 'invite_link' && (
          <div className={styles.selectGroup}>
            {loadingLinks ? (
              <div className={styles.infoText}>Загрузка ссылок...</div>
            ) : (
              <select
                className={styles.select}
                value={targetInviteLinkId ?? ''}
                onChange={(e) => onInviteLinkChange(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Выберите ссылку</option>
                {inviteLinks.map((link) => (
                  <option key={link.id} value={link.id}>
                    {link.name} ({link.users_count} польз.)
                  </option>
                ))}
              </select>
            )}
          </div>
        )}

        {targetType === 'funnel_stage' && (
          <div className={styles.selectGroup}>
            {loadingFunnels ? (
              <div className={styles.infoText}>Загрузка воронок...</div>
            ) : (
              <>
                <select
                  className={styles.select}
                  value={targetFunnelId ?? ''}
                  onChange={(e) => onFunnelChange(e.target.value || null)}
                >
                  <option value="">Выберите воронку</option>
                  {funnels.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.icon} {f.title}
                    </option>
                  ))}
                </select>

                {targetFunnelId && (
                  loadingStages ? (
                    <div className={styles.infoText}>Загрузка этапов...</div>
                  ) : (
                    <select
                      className={styles.select}
                      value={targetStageKey ?? ''}
                      onChange={(e) => onStageChange(e.target.value || null)}
                    >
                      <option value="">Все этапы воронки</option>
                      {stages.map((s) => (
                        <option key={s.stage_key} value={s.stage_key}>
                          {s.title}
                        </option>
                      ))}
                    </select>
                  )
                )}
              </>
            )}
          </div>
        )}

        {targetType === 'manual' && (
          <ManualUserPicker
            selectedIds={targetUserIds}
            onSelectedChange={onUserIdsChange}
          />
        )}
      </div>

      {/* Preview count */}
      {recipientPreviewCount !== null && (
        <div className={styles.previewCount}>
          ~{recipientPreviewCount} получателей
        </div>
      )}
    </div>
  )
}
