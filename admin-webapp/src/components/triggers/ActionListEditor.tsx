// ActionListEditor — Step 3: sequential list of actions

import { useState, useEffect } from 'react'
import { api } from '@/services/api'
import { useFunnelStore } from '@/store/funnelStore'
import { useBroadcastStore } from '@/store/broadcastStore'
import type { TriggerAction, TriggerActionType, FunnelStage, ClientTag } from '@/types'
import styles from './ActionListEditor.module.css'

const ACTION_TYPE_LABELS: Record<TriggerActionType, string> = {
  send_broadcast: 'Отправить рассылку',
  move_to_stage: 'Переместить по воронке',
  add_tag: 'Добавить тег',
  remove_tag: 'Удалить тег',
  set_custom_field: 'Изменить поле',
  send_payment_offer: 'Отправить оплату (подписка)',
  send_quiz_payment: 'Оплата презентации + флагман',
}

interface Props {
  actions: TriggerAction[]
  onChange: (actions: TriggerAction[]) => void
}

type QuizPlan = { problem_key: string; culture: string; problem: string; price_rub: number }

export function ActionListEditor({ actions, onChange }: Props) {
  const { funnels } = useFunnelStore()
  const { broadcasts, fetchBroadcasts } = useBroadcastStore()
  const [tags, setTags] = useState<ClientTag[]>([])
  const [stagesMap, setStagesMap] = useState<Record<string, FunnelStage[]>>({})
  const [plans, setPlans] = useState<{ id: number; name: string; price_rub: number }[]>([])
  const [quizPlans, setQuizPlans] = useState<QuizPlan[]>([])

  useEffect(() => {
    api.getTags().then(setTags).catch(() => {})
    fetchBroadcasts()
    api.getSubscriptionPlans().then(data => {
      setPlans(data.plans.filter((p: any) => p.is_active))
    }).catch(() => {})
    api.getAvailableProducts().then(data => {
      setQuizPlans(data.quiz_plans || [])
    }).catch(() => {})
  }, [fetchBroadcasts])

  const loadStages = async (funnelId: string) => {
    if (stagesMap[funnelId]) return
    try {
      const data = await api.getFunnelStages(funnelId)
      setStagesMap(prev => ({ ...prev, [funnelId]: data.stages }))
    } catch {}
  }

  const addAction = () => {
    onChange([...actions, { type: 'send_broadcast' }])
  }

  const removeAction = (idx: number) => {
    onChange(actions.filter((_, i) => i !== idx))
  }

  const updateAction = (idx: number, action: TriggerAction) => {
    onChange(actions.map((a, i) => (i === idx ? action : a)))
  }

  const handleTypeChange = (idx: number, newType: TriggerActionType) => {
    // Reset to bare action with new type
    updateAction(idx, { type: newType })
  }

  const renderFields = (action: TriggerAction, idx: number) => {
    switch (action.type) {
      case 'send_broadcast':
        return (
          <div className={styles.actionFields}>
            <div className={styles.actionFieldRow}>
              <span className={styles.actionFieldLabel}>Рассылка</span>
              <select
                className={styles.actionFieldSelect}
                value={action.broadcast_id || ''}
                onChange={e => updateAction(idx, { ...action, broadcast_id: e.target.value ? Number(e.target.value) : undefined })}
              >
                <option value="">Выберите рассылку</option>
                {broadcasts.map(b => (
                  <option key={b.id} value={b.id}>{b.title || `#${b.id}`}</option>
                ))}
              </select>
            </div>
          </div>
        )

      case 'move_to_stage':
        return (
          <div className={styles.actionFields}>
            <div className={styles.actionFieldRow}>
              <span className={styles.actionFieldLabel}>Воронка</span>
              <select
                className={styles.actionFieldSelect}
                value={action.funnel_id || ''}
                onChange={e => {
                  const fid = e.target.value
                  updateAction(idx, { ...action, funnel_id: fid || undefined, stage_key: undefined })
                  if (fid) loadStages(fid)
                }}
              >
                <option value="">Выберите</option>
                {funnels.map(f => (
                  <option key={f.id} value={f.id}>{f.title}</option>
                ))}
              </select>
            </div>
            {action.funnel_id && (
              <div className={styles.actionFieldRow}>
                <span className={styles.actionFieldLabel}>Этап</span>
                <select
                  className={styles.actionFieldSelect}
                  value={action.stage_key || ''}
                  onChange={e => updateAction(idx, { ...action, stage_key: e.target.value || undefined })}
                >
                  <option value="">Выберите</option>
                  {(stagesMap[action.funnel_id] || []).map(s => (
                    <option key={s.stage_key} value={s.stage_key}>{s.title}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
        )

      case 'add_tag':
      case 'remove_tag':
        return (
          <div className={styles.actionFields}>
            <div className={styles.actionFieldRow}>
              <span className={styles.actionFieldLabel}>Тег</span>
              <select
                className={styles.actionFieldSelect}
                value={action.tag_id || ''}
                onChange={e => updateAction(idx, { ...action, tag_id: e.target.value ? Number(e.target.value) : undefined })}
              >
                <option value="">Выберите тег</option>
                {tags.map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
          </div>
        )

      case 'set_custom_field':
        return (
          <div className={styles.actionFields}>
            <div className={styles.actionFieldRow}>
              <span className={styles.actionFieldLabel}>Поле ID</span>
              <input
                type="number"
                className={styles.actionFieldInput}
                value={action.field_id || ''}
                onChange={e => updateAction(idx, { ...action, field_id: e.target.value ? Number(e.target.value) : undefined })}
                placeholder="ID поля"
              />
            </div>
            <div className={styles.actionFieldRow}>
              <span className={styles.actionFieldLabel}>Значение</span>
              <input
                type="text"
                className={styles.actionFieldInput}
                value={action.value || ''}
                onChange={e => updateAction(idx, { ...action, value: e.target.value })}
                placeholder="Новое значение"
              />
            </div>
          </div>
        )

      case 'send_payment_offer':
        return (
          <div className={styles.actionFields}>
            <div className={styles.actionFieldRow}>
              <span className={styles.actionFieldLabel}>План</span>
              <select
                className={styles.actionFieldSelect}
                value={action.plan_id || ''}
                onChange={e => updateAction(idx, { ...action, plan_id: e.target.value ? Number(e.target.value) : undefined })}
              >
                <option value="">Выберите план</option>
                {plans.map(p => (
                  <option key={p.id} value={p.id}>{p.name} ({p.price_rub} руб.)</option>
                ))}
              </select>
            </div>
            <div className={styles.actionFieldRow}>
              <span className={styles.actionFieldLabel}>Цена</span>
              <input
                type="number"
                className={styles.actionFieldInput}
                value={action.custom_price ?? ''}
                onChange={e => updateAction(idx, { ...action, custom_price: e.target.value ? Number(e.target.value) : undefined })}
                placeholder="По умолчанию из плана"
              />
            </div>
            <div className={styles.actionFieldRow}>
              <span className={styles.actionFieldLabel}>Бонус</span>
              <input
                type="number"
                className={styles.actionFieldInput}
                value={action.bonus_tokens ?? ''}
                onChange={e => updateAction(idx, { ...action, bonus_tokens: e.target.value ? Number(e.target.value) : undefined })}
                placeholder="Бонусные токены"
              />
            </div>
          </div>
        )

      case 'send_quiz_payment': {
        // Группировка по культуре
        const groups: Record<string, QuizPlan[]> = {}
        for (const p of quizPlans) {
          if (!groups[p.culture]) groups[p.culture] = []
          groups[p.culture].push(p)
        }
        const customPrice = action.custom_price
        return (
          <div className={styles.actionFields}>
            <div className={styles.actionFieldRow}>
              <span className={styles.actionFieldLabel}>Презентация</span>
              <select
                className={styles.actionFieldSelect}
                value={action.problem_key || ''}
                onChange={e => updateAction(idx, { ...action, problem_key: e.target.value || undefined })}
              >
                <option value="">По квизу пользователя</option>
                {Object.entries(groups).map(([culture, items]) => (
                  <optgroup key={culture} label={culture}>
                    {items.map(item => (
                      <option key={item.problem_key} value={item.problem_key}>
                        {item.problem}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
            <div className={styles.actionFieldRow}>
              <span className={styles.actionFieldLabel}>Цена ₽</span>
              <input
                type="number"
                className={styles.actionFieldInput}
                value={customPrice ?? ''}
                onChange={e => updateAction(idx, { ...action, custom_price: e.target.value ? Number(e.target.value) : undefined })}
                placeholder="99 (по умолчанию)"
                min={1}
              />
              {customPrice && customPrice < 99 && (
                <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 6 }}>
                  скидка {Math.round((1 - customPrice / 99) * 100)}%
                </span>
              )}
            </div>
            <div className={styles.actionFieldRow}>
              <span className={styles.actionFieldLabel}>Опрос после оплаты</span>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={!!action.send_quiz_after_payment}
                  onChange={e => updateAction(idx, { ...action, send_quiz_after_payment: e.target.checked || undefined })}
                />
                <span style={{ fontSize: 13 }}>Запустить опрос №2 через 90 сек</span>
              </label>
            </div>
            <div className={styles.actionFieldRow}>
              <span className={styles.actionFieldLabel}>Сообщение</span>
              <input
                type="text"
                className={styles.actionFieldInput}
                value={action.custom_message || ''}
                onChange={e => updateAction(idx, { ...action, custom_message: e.target.value || undefined })}
                placeholder="Текст перед оффером (необязательно)"
              />
            </div>
          </div>
        )
      }

      default:
        return null
    }
  }

  return (
    <div className={styles.editor}>
      {actions.length === 0 && (
        <div className={styles.emptyHint}>
          Добавьте хотя бы одно действие
        </div>
      )}

      {actions.map((action, idx) => (
        <div key={idx} className={styles.actionCard}>
          <div className={styles.actionHeader}>
            <span className={styles.actionIndex}>{idx + 1}</span>
            <select
              className={styles.actionTypeSelect}
              value={action.type}
              onChange={e => handleTypeChange(idx, e.target.value as TriggerActionType)}
            >
              {Object.entries(ACTION_TYPE_LABELS).map(([val, label]) => (
                <option key={val} value={val}>{label}</option>
              ))}
            </select>
            <button
              className={styles.removeActionButton}
              onClick={() => removeAction(idx)}
              title="Удалить действие"
            >
              &times;
            </button>
          </div>
          {renderFields(action, idx)}
        </div>
      ))}

      <button className={styles.addActionButton} onClick={addAction}>
        + Добавить действие
      </button>
    </div>
  )
}
