// TriggerEditor — 3-step form: Event → Conditions → Actions

import { useState, useEffect } from 'react'
import { useTriggerStore } from '@/store/triggerStore'
import type {
  AutomationTrigger,
  TriggerEventType,
  TriggerAction,
  ConditionTree,
  CreateTriggerDto,
} from '@/types'
import { EventTypeSelector } from './EventTypeSelector'
import { ConditionBuilder } from './ConditionBuilder'
import { ActionListEditor } from './ActionListEditor'
import styles from './TriggerEditor.module.css'

interface Props {
  trigger: AutomationTrigger | null // null = create mode
  onSaved: () => void
  onCancel: () => void
}

export function TriggerEditor({ trigger, onSaved, onCancel }: Props) {
  const { createTrigger, updateTrigger, deleteTrigger } = useTriggerStore()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [eventType, setEventType] = useState<TriggerEventType>('stage_transition')
  const [eventConfig, setEventConfig] = useState<Record<string, any>>({ funnel_id: '', stage_key: '' })
  const [conditions, setConditions] = useState<ConditionTree | null>(null)
  const [actions, setActions] = useState<TriggerAction[]>([])
  const [delayHours, setDelayHours] = useState(0)
  const [delayMinutes, setDelayMinutes] = useState(0)
  const [saving, setSaving] = useState(false)

  // Populate form when editing
  useEffect(() => {
    if (trigger) {
      setName(trigger.name)
      setDescription(trigger.description || '')
      setEventType(trigger.event_type)
      setEventConfig(trigger.event_config)
      setConditions(trigger.conditions)
      setActions(trigger.actions)
      const totalMin = trigger.delay_minutes || 0
      setDelayHours(Math.floor(totalMin / 60))
      setDelayMinutes(totalMin % 60)
    }
  }, [trigger])

  const handleEventChange = (type: TriggerEventType, config: Record<string, any>) => {
    setEventType(type)
    setEventConfig(config)
  }

  const isValid = () => {
    if (!name.trim()) return false
    if (actions.length === 0) return false
    // Validate event config
    if (eventType === 'stage_transition' && (!eventConfig.funnel_id || !eventConfig.stage_key)) return false
    if (eventType === 'tag_changed' && !eventConfig.tag_id) return false
    return true
  }

  const handleSave = async () => {
    if (!isValid()) return
    setSaving(true)

    const dto: CreateTriggerDto = {
      name: name.trim(),
      description: description.trim() || undefined,
      event_type: eventType,
      event_config: eventConfig,
      conditions: conditions,
      actions,
      delay_minutes: delayHours * 60 + delayMinutes,
    }

    try {
      if (trigger) {
        await updateTrigger(trigger.id, dto)
      } else {
        await createTrigger(dto)
      }
      onSaved()
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!trigger) return
    if (!confirm('Удалить триггер? Это действие необратимо.')) return
    await deleteTrigger(trigger.id)
    onCancel()
  }

  return (
    <div className={styles.editor}>
      <h3 className={styles.editorTitle}>
        {trigger ? 'Редактировать триггер' : 'Новый триггер'}
      </h3>

      {/* Name + Description */}
      <div className={styles.field}>
        <label className={styles.fieldLabel}>Название</label>
        <input
          className={styles.fieldInput}
          type="text"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Например: Приветственное сообщение после оплаты"
        />
      </div>
      <div className={styles.field}>
        <label className={styles.fieldLabel}>Описание</label>
        <textarea
          className={styles.fieldTextarea}
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="Необязательное описание для заметок"
          rows={2}
        />
      </div>

      {/* Step 1: Event */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>
          <span className={styles.stepNumber}>1</span>
          Событие
        </h4>
        <EventTypeSelector
          eventType={eventType}
          eventConfig={eventConfig}
          onChange={handleEventChange}
        />
      </div>

      {/* Step 2: Conditions */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>
          <span className={styles.stepNumber}>2</span>
          Условия (опционально)
        </h4>
        <ConditionBuilder conditions={conditions} onChange={setConditions} />
      </div>

      {/* Step 3: Actions */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>
          <span className={styles.stepNumber}>3</span>
          Действия
        </h4>
        <ActionListEditor actions={actions} onChange={setActions} />
      </div>

      {/* Delay */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Задержка</h4>
        <div className={styles.delayRow}>
          <input
            type="number"
            className={styles.delayInput}
            value={delayHours}
            min={0}
            max={168}
            onChange={e => setDelayHours(Number(e.target.value) || 0)}
          />
          <span className={styles.delayLabel}>ч</span>
          <input
            type="number"
            className={styles.delayInput}
            value={delayMinutes}
            min={0}
            max={59}
            onChange={e => setDelayMinutes(Number(e.target.value) || 0)}
          />
          <span className={styles.delayLabel}>мин</span>
          {(delayHours > 0 || delayMinutes > 0) && (
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: '8px' }}>
              = {delayHours * 60 + delayMinutes} мин.
            </span>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className={styles.footer}>
        {trigger && (
          <button className={styles.deleteButton} onClick={handleDelete}>
            Удалить
          </button>
        )}
        <button className={styles.cancelButton} onClick={onCancel}>
          Отмена
        </button>
        <button
          className={styles.saveButton}
          onClick={handleSave}
          disabled={!isValid() || saving}
        >
          {saving ? 'Сохранение...' : trigger ? 'Сохранить' : 'Создать'}
        </button>
      </div>
    </div>
  )
}
