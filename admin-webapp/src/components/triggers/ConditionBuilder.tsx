// ConditionBuilder — Step 2: AND/OR condition groups

import { useState, useEffect } from 'react'
import { api } from '@/services/api'
import { useFunnelStore } from '@/store/funnelStore'
import { useTriggerStore } from '@/store/triggerStore'
import type { ConditionTree, ConditionGroup, ConditionRule, FunnelStage, ClientTag } from '@/types'
import styles from './ConditionBuilder.module.css'

const RULE_TYPE_LABELS: Record<ConditionRule['type'], string> = {
  has_tag: 'Есть тег',
  not_has_tag: 'Нет тега',
  from_invite_link: 'Пришёл по ссылке',
  at_funnel_stage: 'На этапе воронки',
  not_at_funnel_stage: 'Не на этапе воронки',
}

interface Props {
  conditions: ConditionTree | null
  onChange: (conditions: ConditionTree | null) => void
}

export function ConditionBuilder({ conditions, onChange }: Props) {
  const { funnels } = useFunnelStore()
  const { previewUsers } = useTriggerStore()
  const [tags, setTags] = useState<ClientTag[]>([])
  const [inviteLinks, setInviteLinks] = useState<{ id: number; name: string }[]>([])
  const [stagesMap, setStagesMap] = useState<Record<string, FunnelStage[]>>({})
  const [previewCount, setPreviewCount] = useState<number | null>(null)

  // Load reference data
  useEffect(() => {
    api.getTags().then(setTags).catch(() => {})
    api.getInviteLinks().then(data => setInviteLinks(data.links || data)).catch(() => {})
  }, [])

  // Helper to ensure we have a tree
  const tree: ConditionTree = conditions || { operator: 'AND', groups: [] }

  const updateTree = (updated: ConditionTree) => {
    // If no groups, set to null (no conditions)
    if (updated.groups.length === 0) {
      onChange(null)
    } else {
      onChange(updated)
    }
  }

  const setTopOperator = (op: 'AND' | 'OR') => {
    updateTree({ ...tree, operator: op })
  }

  const addGroup = () => {
    updateTree({
      ...tree,
      groups: [...tree.groups, { operator: 'AND', rules: [{ type: 'has_tag' }] }],
    })
  }

  const removeGroup = (gi: number) => {
    updateTree({ ...tree, groups: tree.groups.filter((_, i) => i !== gi) })
  }

  const updateGroup = (gi: number, group: ConditionGroup) => {
    updateTree({
      ...tree,
      groups: tree.groups.map((g, i) => (i === gi ? group : g)),
    })
  }

  const setGroupOperator = (gi: number, op: 'AND' | 'OR') => {
    updateGroup(gi, { ...tree.groups[gi], operator: op })
  }

  const addRule = (gi: number) => {
    const group = tree.groups[gi]
    updateGroup(gi, { ...group, rules: [...group.rules, { type: 'has_tag' }] })
  }

  const removeRule = (gi: number, ri: number) => {
    const group = tree.groups[gi]
    const newRules = group.rules.filter((_, i) => i !== ri)
    if (newRules.length === 0) {
      removeGroup(gi)
    } else {
      updateGroup(gi, { ...group, rules: newRules })
    }
  }

  const updateRule = (gi: number, ri: number, rule: ConditionRule) => {
    const group = tree.groups[gi]
    updateGroup(gi, {
      ...group,
      rules: group.rules.map((r, i) => (i === ri ? rule : r)),
    })
  }

  // Load stages for funnel-related rules
  const loadStages = async (funnelId: string) => {
    if (stagesMap[funnelId]) return
    try {
      const data = await api.getFunnelStages(funnelId)
      setStagesMap(prev => ({ ...prev, [funnelId]: data.stages }))
    } catch {}
  }

  const handlePreview = async () => {
    if (!conditions) {
      setPreviewCount(null)
      return
    }
    const count = await previewUsers(conditions)
    setPreviewCount(count)
  }

  const renderRuleValue = (rule: ConditionRule, gi: number, ri: number) => {
    const ruleType = rule.type

    if (ruleType === 'has_tag' || ruleType === 'not_has_tag') {
      return (
        <select
          className={styles.ruleValue}
          value={rule.tag_id || ''}
          onChange={e => updateRule(gi, ri, { ...rule, tag_id: e.target.value ? Number(e.target.value) : undefined })}
        >
          <option value="">Выберите тег</option>
          {tags.map(t => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
      )
    }

    if (ruleType === 'from_invite_link') {
      return (
        <select
          className={styles.ruleValue}
          value={rule.invite_link_id || ''}
          onChange={e => updateRule(gi, ri, { ...rule, invite_link_id: e.target.value ? Number(e.target.value) : undefined })}
        >
          <option value="">Выберите ссылку</option>
          {inviteLinks.map(l => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
        </select>
      )
    }

    if (ruleType === 'at_funnel_stage' || ruleType === 'not_at_funnel_stage') {
      return (
        <>
          <select
            className={styles.ruleValue}
            value={rule.funnel_id || ''}
            onChange={e => {
              const fid = e.target.value
              updateRule(gi, ri, { ...rule, funnel_id: fid || undefined, stage_key: undefined })
              if (fid) loadStages(fid)
            }}
          >
            <option value="">Воронка</option>
            {funnels.map(f => (
              <option key={f.id} value={f.id}>{f.title}</option>
            ))}
          </select>
          {rule.funnel_id && (
            <select
              className={styles.ruleValue}
              value={rule.stage_key || ''}
              onChange={e => updateRule(gi, ri, { ...rule, stage_key: e.target.value || undefined })}
            >
              <option value="">Этап</option>
              {(stagesMap[rule.funnel_id] || []).map(s => (
                <option key={s.stage_key} value={s.stage_key}>{s.title}</option>
              ))}
            </select>
          )}
        </>
      )
    }

    return null
  }

  return (
    <div className={styles.builder}>
      {tree.groups.length === 0 ? (
        <div className={styles.emptyHint}>
          Без условий — триггер сработает для всех пользователей
        </div>
      ) : (
        <>
          {/* Top-level AND/OR */}
          {tree.groups.length > 1 && (
            <div className={styles.topOperator}>
              <span className={styles.topOperatorLabel}>Между группами:</span>
              <OperatorToggle value={tree.operator} onChange={setTopOperator} />
            </div>
          )}

          {/* Groups */}
          {tree.groups.map((group, gi) => (
            <div key={gi}>
              {gi > 0 && (
                <div className={styles.groupDivider}>{tree.operator}</div>
              )}
              <div className={styles.group}>
                <div className={styles.groupHeader}>
                  <div className={styles.groupHeaderLeft}>
                    <span className={styles.groupLabel}>Группа {gi + 1}</span>
                    {group.rules.length > 1 && (
                      <OperatorToggle
                        value={group.operator}
                        onChange={op => setGroupOperator(gi, op)}
                      />
                    )}
                  </div>
                  <button
                    className={styles.removeGroupButton}
                    onClick={() => removeGroup(gi)}
                    title="Удалить группу"
                  >
                    &times;
                  </button>
                </div>

                <div className={styles.rules}>
                  {group.rules.map((rule, ri) => (
                    <div key={ri} className={styles.rule}>
                      <select
                        className={styles.ruleSelect}
                        value={rule.type}
                        onChange={e => updateRule(gi, ri, { type: e.target.value as ConditionRule['type'] })}
                      >
                        {Object.entries(RULE_TYPE_LABELS).map(([val, label]) => (
                          <option key={val} value={val}>{label}</option>
                        ))}
                      </select>
                      {renderRuleValue(rule, gi, ri)}
                      <button
                        className={styles.removeRuleButton}
                        onClick={() => removeRule(gi, ri)}
                        title="Удалить правило"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                </div>

                <button className={styles.addRuleButton} onClick={() => addRule(gi)}>
                  + Правило
                </button>
              </div>
            </div>
          ))}
        </>
      )}

      <button className={styles.addGroupButton} onClick={addGroup}>
        + Добавить группу условий
      </button>

      {/* Preview */}
      {conditions && conditions.groups.length > 0 && (
        <div className={styles.previewRow}>
          <button className={styles.previewButton} onClick={handlePreview}>
            Проверить
          </button>
          {previewCount !== null && (
            <span className={styles.previewResult}>
              {previewCount} клиентов подходят
            </span>
          )}
        </div>
      )}
    </div>
  )
}

// Inline operator AND/OR toggle
function OperatorToggle({ value, onChange }: { value: 'AND' | 'OR'; onChange: (v: 'AND' | 'OR') => void }) {
  return (
    <div className={styles.operatorToggle}>
      <button
        className={`${styles.operatorOption} ${value === 'AND' ? styles.operatorOptionActive : ''}`}
        onClick={() => onChange('AND')}
      >
        И
      </button>
      <button
        className={`${styles.operatorOption} ${value === 'OR' ? styles.operatorOptionActive : ''}`}
        onClick={() => onChange('OR')}
      >
        ИЛИ
      </button>
    </div>
  )
}
