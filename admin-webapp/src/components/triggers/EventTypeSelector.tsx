// EventTypeSelector — Step 1: choose event type + configure event_config

import { useState, useEffect } from 'react'
import { api } from '@/services/api'
import type { TriggerEventType, FunnelStage } from '@/types'
import { useFunnelStore } from '@/store/funnelStore'
import styles from './TriggerEditor.module.css'

const EVENT_LABELS: Record<TriggerEventType, string> = {
  stage_transition: 'Переход по этапу воронки',
  payment_success: 'Успешная оплата',
  tag_changed: 'Изменение тега',
  subscription_expiring: 'Истечение подписки',
}

interface Props {
  eventType: TriggerEventType
  eventConfig: Record<string, any>
  onChange: (eventType: TriggerEventType, eventConfig: Record<string, any>) => void
}

export function EventTypeSelector({ eventType, eventConfig, onChange }: Props) {
  const { funnels } = useFunnelStore()
  const [stages, setStages] = useState<FunnelStage[]>([])
  const [tags, setTags] = useState<{ id: number; name: string }[]>([])

  // Load stages when funnel changes
  useEffect(() => {
    const funnelId = eventConfig.funnel_id
    if (funnelId && eventType === 'stage_transition') {
      api.getFunnelStages(funnelId).then(data => setStages(data.stages)).catch(() => {})
    } else {
      setStages([])
    }
  }, [eventConfig.funnel_id, eventType])

  // Load tags for tag_changed event
  useEffect(() => {
    if (eventType === 'tag_changed') {
      api.getTags().then(data => setTags(data)).catch(() => {})
    }
  }, [eventType])

  const handleTypeChange = (newType: TriggerEventType) => {
    // Reset config when type changes
    const defaults: Record<TriggerEventType, Record<string, any>> = {
      stage_transition: { funnel_id: '', stage_key: '' },
      payment_success: { payment_type: 'any' },
      tag_changed: { tag_id: null, action: 'added' },
      subscription_expiring: { days_before: 3 },
    }
    onChange(newType, defaults[newType])
  }

  const updateConfig = (patch: Record<string, any>) => {
    onChange(eventType, { ...eventConfig, ...patch })
  }

  return (
    <div>
      {/* Event type radio buttons */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '14px' }}>
        {(Object.keys(EVENT_LABELS) as TriggerEventType[]).map(type => (
          <label
            key={type}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-start',
              gap: '8px',
              padding: '8px 12px',
              background: eventType === type ? 'rgba(74, 124, 89, 0.06)' : 'transparent',
              border: `1px solid ${eventType === type ? 'var(--accent-primary)' : 'var(--border-default)'}`,
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '13px',
              transition: 'all 0.15s ease',
              userSelect: 'none',
            }}
          >
            <input
              type="radio"
              name="event_type"
              checked={eventType === type}
              onChange={() => handleTypeChange(type)}
              style={{ accentColor: 'var(--accent-primary)', width: 'auto', flexShrink: 0 }}
            />
            {EVENT_LABELS[type]}
          </label>
        ))}
      </div>

      {/* Event config fields */}
      {eventType === 'stage_transition' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div>
            <label className={styles.fieldLabel}>Воронка</label>
            <select
              className={styles.fieldInput}
              value={eventConfig.funnel_id || ''}
              onChange={e => updateConfig({ funnel_id: e.target.value, stage_key: '' })}
            >
              <option value="">Выберите воронку</option>
              {funnels.map(f => (
                <option key={f.id} value={f.id}>{f.title}</option>
              ))}
            </select>
          </div>
          {eventConfig.funnel_id && (
            <div>
              <label className={styles.fieldLabel}>Этап</label>
              <select
                className={styles.fieldInput}
                value={eventConfig.stage_key || ''}
                onChange={e => updateConfig({ stage_key: e.target.value })}
              >
                <option value="">Выберите этап</option>
                {stages.map(s => (
                  <option key={s.stage_key} value={s.stage_key}>{s.title}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}

      {eventType === 'payment_success' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div>
            <label className={styles.fieldLabel}>Тип платежа</label>
            <select
              className={styles.fieldInput}
              value={eventConfig.payment_type || 'any'}
              onChange={e => updateConfig({ payment_type: e.target.value })}
            >
              <option value="any">Любой</option>
              <option value="subscription">Подписка</option>
              <option value="tokens">Токены</option>
            </select>
          </div>
          {eventConfig.payment_type === 'subscription' && (
            <div>
              <label className={styles.fieldLabel}>План (опционально)</label>
              <PlanSelector
                value={eventConfig.plan_id}
                onChange={planId => updateConfig({ plan_id: planId })}
              />
            </div>
          )}
        </div>
      )}

      {eventType === 'tag_changed' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div>
            <label className={styles.fieldLabel}>Тег</label>
            <select
              className={styles.fieldInput}
              value={eventConfig.tag_id || ''}
              onChange={e => updateConfig({ tag_id: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">Выберите тег</option>
              {tags.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={styles.fieldLabel}>Действие</label>
            <select
              className={styles.fieldInput}
              value={eventConfig.action || 'added'}
              onChange={e => updateConfig({ action: e.target.value })}
            >
              <option value="added">Добавлен</option>
              <option value="removed">Удалён</option>
            </select>
          </div>
        </div>
      )}

      {eventType === 'subscription_expiring' && (
        <div>
          <label className={styles.fieldLabel}>За сколько дней до истечения</label>
          <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', flexWrap: 'wrap' }}>
            {[0, 1, 3, 7].map(d => (
              <button
                key={d}
                type="button"
                onClick={() => updateConfig({ days_before: d })}
                style={{
                  padding: '4px 12px',
                  border: `1px solid ${eventConfig.days_before === d ? 'var(--accent-primary)' : 'var(--border-default)'}`,
                  borderRadius: '6px',
                  background: eventConfig.days_before === d ? 'rgba(74, 124, 89, 0.1)' : 'transparent',
                  color: eventConfig.days_before === d ? 'var(--accent-primary)' : 'var(--text-secondary)',
                  fontSize: '12px',
                  fontWeight: eventConfig.days_before === d ? 600 : 400,
                  cursor: 'pointer',
                }}
              >
                {d === 0 ? 'В момент' : `${d} дн.`}
              </button>
            ))}
          </div>
          <input
            type="number"
            className={styles.fieldInput}
            value={eventConfig.days_before ?? 3}
            min={0}
            max={30}
            onChange={e => updateConfig({ days_before: Number(e.target.value) })}
            style={{ width: '100px' }}
          />
        </div>
      )}
    </div>
  )
}

// Mini component for subscription plan selection
function PlanSelector({ value, onChange }: { value?: number; onChange: (id: number | undefined) => void }) {
  const [plans, setPlans] = useState<{ id: number; name: string; price_rub: number }[]>([])

  useEffect(() => {
    api.getSubscriptionPlans().then(data => {
      setPlans(data.plans.filter((p: any) => p.is_active))
    }).catch(() => {})
  }, [])

  return (
    <select
      className={styles.fieldInput}
      value={value || ''}
      onChange={e => onChange(e.target.value ? Number(e.target.value) : undefined)}
    >
      <option value="">Любой план</option>
      {plans.map(p => (
        <option key={p.id} value={p.id}>{p.name} ({p.price_rub} руб.)</option>
      ))}
    </select>
  )
}
