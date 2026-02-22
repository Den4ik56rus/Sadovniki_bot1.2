// Stage Trigger Editor — управление триггерами рассылок на этапе воронки

import { useState, useEffect } from 'react'
import { useFunnelStore } from '@/store/funnelStore'
import { api } from '@/services/api'
import type { Broadcast, FunnelStageTrigger } from '@/types'
import styles from './StageTriggerEditor.module.css'

interface Props {
  funnelId: string
  stageKey: string
  triggers: FunnelStageTrigger[]
}

export function StageTriggerEditor({ funnelId, stageKey, triggers }: Props) {
  const { createTrigger, deleteTrigger, toggleTrigger } = useFunnelStore()
  const [broadcasts, setBroadcasts] = useState<Broadcast[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedBroadcastId, setSelectedBroadcastId] = useState<number | null>(null)
  const [isAdding, setIsAdding] = useState(false)

  // Load broadcasts for selection
  useEffect(() => {
    if (isAdding && broadcasts.length === 0) {
      setLoading(true)
      api.getBroadcasts().then((data) => {
        // Показываем рассылки с контентом (не пустые черновики)
        setBroadcasts(data.broadcasts.filter((b) =>
          b.message_text || b.photo_path || b.poll_question
        ))
      }).catch(() => {}).finally(() => setLoading(false))
    }
  }, [isAdding, broadcasts.length])

  const handleAdd = async () => {
    if (!selectedBroadcastId) return
    const ok = await createTrigger(funnelId, stageKey, selectedBroadcastId)
    if (ok) {
      setIsAdding(false)
      setSelectedBroadcastId(null)
    }
  }

  const handleDelete = async (triggerId: number) => {
    if (!confirm('Удалить триггер?')) return
    await deleteTrigger(triggerId)
  }

  const handleToggle = async (trigger: FunnelStageTrigger) => {
    await toggleTrigger(trigger.id, !trigger.is_active)
  }

  const stageTriggers = triggers.filter((t) => t.stage_key === stageKey)

  // IDs рассылок, которые уже привязаны
  const usedBroadcastIds = new Set(stageTriggers.map((t) => t.broadcast_id))

  return (
    <div className={styles.container}>
      {/* Existing triggers */}
      {stageTriggers.map((trigger) => (
        <div key={trigger.id} className={`${styles.triggerCard} ${!trigger.is_active ? styles.triggerCardDisabled : ''}`}>
          <div className={styles.triggerInfo}>
            <span className={styles.triggerIcon}>⚡</span>
            <div className={styles.triggerText}>
              <span className={styles.triggerTitle}>{trigger.broadcast_title}</span>
              <span className={styles.triggerStatus}>
                {trigger.is_active ? 'Активен' : 'Выключен'}
              </span>
            </div>
          </div>
          <div className={styles.triggerActions}>
            <button
              className={`${styles.toggleBtn} ${trigger.is_active ? styles.toggleBtnActive : ''}`}
              onClick={() => handleToggle(trigger)}
              title={trigger.is_active ? 'Выключить' : 'Включить'}
            >
              <div className={styles.toggleTrack}>
                <div className={styles.toggleThumb} />
              </div>
            </button>
            <button
              className={styles.deleteTriggerBtn}
              onClick={() => handleDelete(trigger.id)}
              title="Удалить"
            >
              ✕
            </button>
          </div>
        </div>
      ))}

      {/* Add trigger form */}
      {isAdding ? (
        <div className={styles.addForm}>
          {loading ? (
            <div className={styles.loadingText}>Загрузка рассылок...</div>
          ) : (
            <>
              <select
                className={styles.selectBroadcast}
                value={selectedBroadcastId ?? ''}
                onChange={(e) => setSelectedBroadcastId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Выберите рассылку</option>
                {broadcasts
                  .filter((b) => !usedBroadcastIds.has(b.id))
                  .map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.title || `#${b.id}`}
                    </option>
                  ))}
              </select>
              <div className={styles.addFormActions}>
                <button
                  className={styles.confirmAddBtn}
                  onClick={handleAdd}
                  disabled={!selectedBroadcastId}
                >
                  Добавить
                </button>
                <button
                  className={styles.cancelAddBtn}
                  onClick={() => { setIsAdding(false); setSelectedBroadcastId(null) }}
                >
                  Отмена
                </button>
              </div>
            </>
          )}
        </div>
      ) : (
        <button
          className={styles.addTriggerBtn}
          onClick={() => setIsAdding(true)}
        >
          + Добавить триггер
        </button>
      )}
    </div>
  )
}
