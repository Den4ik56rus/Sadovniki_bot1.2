/**
 * Дерево групп и подгрупп промптов.
 *
 * Отображает иерархию:
 * - Группа (раскрывающаяся)
 *   - Подгруппа (раскрывающаяся)
 *     - [Для prompt_docs: Тип культуры (летняя, рем, общее, ежевика)]
 *       - Промпт (кликабельный)
 *     - Промпт без подтипа
 *   - Промпт без подгруппы
 */

import { usePromptStore } from '@/store/promptStore'
import { setParams } from '@/router'
import type { PromptGroup, PromptSubgroup, Prompt } from '@/types'
import styles from './PromptGroupTree.module.css'

// Маппинг префиксов slug на человекочитаемые названия
const CULTURE_TYPE_LABELS: Record<string, string> = {
  summer: 'Летняя',
  remontant: 'Ремонтантная',
  general: 'Общее',
  blackberry: 'Ежевика',
  currant: 'Смородина',
  honeysuckle: 'Жимолость',
}

// Порядок отображения типов культур
const CULTURE_TYPE_ORDER = ['blackberry', 'summer', 'general', 'remontant', 'currant', 'honeysuckle']

// Подгруппы, для которых нужна группировка по типу культуры
const CULTURE_SUBGROUPS = ['strawberry', 'raspberry', 'currant', 'blueberry']

export function PromptGroupTree() {
  const {
    groups,
    prompts,
    selectedPrompt,
    expandedGroups,
    expandedSubgroups,
    expandedCultureTypes,
    toggleGroupExpanded,
    toggleSubgroupExpanded,
    toggleCultureTypeExpanded,
    selectPrompt,
    togglePromptEnabled,
  } = usePromptStore()

  // Get prompts for a specific group and subgroup
  const getPromptsForSubgroup = (groupId: number, subgroupId: number): Prompt[] => {
    return prompts.filter(
      (p) => p.group_id === groupId && p.subgroup_id === subgroupId
    )
  }

  // Get prompts directly under a group (no subgroup)
  const getPromptsWithoutSubgroup = (groupId: number): Prompt[] => {
    return prompts.filter(
      (p) => p.group_id === groupId && p.subgroup_id === null
    )
  }

  // Group prompts by culture type (summer_, remontant_, general_, blackberry_)
  const groupPromptsByCultureType = (promptsList: Prompt[]): Map<string, Prompt[]> => {
    const grouped = new Map<string, Prompt[]>()

    for (const prompt of promptsList) {
      let cultureType = 'other'
      for (const prefix of CULTURE_TYPE_ORDER) {
        if (prompt.slug.startsWith(prefix + '_')) {
          cultureType = prefix
          break
        }
      }

      if (!grouped.has(cultureType)) {
        grouped.set(cultureType, [])
      }
      grouped.get(cultureType)!.push(prompt)
    }

    return grouped
  }

  const handlePromptClick = (prompt: Prompt) => {
    selectPrompt(prompt.id)
    setParams({ prompt: String(prompt.id) })
  }

  const handleToggleEnabled = (e: React.MouseEvent, prompt: Prompt) => {
    e.stopPropagation()
    togglePromptEnabled(prompt.id, !prompt.is_enabled)
  }

  // Получить короткое имя промпта (без префикса типа культуры)
  const getShortPromptName = (prompt: Prompt): string => {
    // Если имя содержит " — ", берём часть после
    if (prompt.name.includes(' — ')) {
      return prompt.name.split(' — ')[1]
    }
    return prompt.name
  }

  const renderPromptItem = (prompt: Prompt, showShortName = false) => {
    const isSelected = selectedPrompt?.id === prompt.id

    return (
      <div
        key={prompt.id}
        className={`${styles.promptItem} ${isSelected ? styles.selected : ''} ${!prompt.is_enabled ? styles.disabled : ''}`}
        onClick={() => handlePromptClick(prompt)}
      >
        <button
          className={`${styles.checkbox} ${prompt.is_enabled ? styles.checked : ''}`}
          onClick={(e) => handleToggleEnabled(e, prompt)}
          title={prompt.is_enabled ? 'Выключить' : 'Включить'}
        >
          {prompt.is_enabled ? '✓' : ''}
        </button>
        <span className={styles.promptName}>
          {showShortName ? getShortPromptName(prompt) : prompt.name}
        </span>
        {prompt.is_system && (
          <span className={styles.systemBadge} title="Системный промпт">
            S
          </span>
        )}
      </div>
    )
  }

  // Render culture type group (летняя, рем, общее, ежевика)
  const renderCultureTypeGroup = (
    subgroupId: number,
    cultureType: string,
    culturePrompts: Prompt[]
  ) => {
    const key = `${subgroupId}-${cultureType}`
    const isExpanded = expandedCultureTypes.has(key)
    const label = CULTURE_TYPE_LABELS[cultureType] || cultureType

    return (
      <div key={cultureType} className={styles.cultureType}>
        <div
          className={styles.cultureTypeHeader}
          onClick={() => toggleCultureTypeExpanded(subgroupId, cultureType)}
        >
          <span className={styles.expandIcon}>{isExpanded ? '▼' : '▶'}</span>
          <span className={styles.cultureTypeName}>{label}</span>
          <span className={styles.count}>{culturePrompts.length}</span>
        </div>

        {isExpanded && (
          <div className={styles.cultureTypeContent}>
            {culturePrompts.map((p) => renderPromptItem(p, true))}
          </div>
        )}
      </div>
    )
  }

  const renderSubgroup = (group: PromptGroup, subgroup: PromptSubgroup) => {
    const key = `${group.id}-${subgroup.id}`
    const isExpanded = expandedSubgroups.has(key)
    const subgroupPrompts = getPromptsForSubgroup(group.id, subgroup.id)

    // Проверяем, нужна ли группировка по типу культуры
    const needsCultureGrouping =
      group.slug === 'prompt_docs' && CULTURE_SUBGROUPS.includes(subgroup.slug)

    return (
      <div key={subgroup.id} className={styles.subgroup}>
        <div
          className={styles.subgroupHeader}
          onClick={() => toggleSubgroupExpanded(group.id, subgroup.id)}
        >
          <span className={styles.expandIcon}>{isExpanded ? '▼' : '▶'}</span>
          <span className={styles.subgroupName}>{subgroup.name}</span>
          <span className={styles.count}>{subgroupPrompts.length}</span>
        </div>

        {isExpanded && (
          <div className={styles.subgroupContent}>
            {needsCultureGrouping ? (
              // Группируем по типу культуры
              (() => {
                const grouped = groupPromptsByCultureType(subgroupPrompts)
                return CULTURE_TYPE_ORDER
                  .filter((ct) => grouped.has(ct))
                  .map((ct) => renderCultureTypeGroup(subgroup.id, ct, grouped.get(ct)!))
              })()
            ) : (
              // Обычное отображение
              <>
                {subgroupPrompts.map((p) => renderPromptItem(p))}
                {subgroupPrompts.length === 0 && (
                  <div className={styles.empty}>Нет промптов</div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    )
  }

  const renderGroup = (group: PromptGroup) => {
    const isExpanded = expandedGroups.has(group.id)
    const directPrompts = getPromptsWithoutSubgroup(group.id)

    return (
      <div key={group.id} className={styles.group}>
        <div
          className={styles.groupHeader}
          onClick={() => toggleGroupExpanded(group.id)}
        >
          <span className={styles.expandIcon}>{isExpanded ? '▼' : '▶'}</span>
          <span className={styles.groupIcon}>{group.icon || '📁'}</span>
          <span className={styles.groupName}>{group.name}</span>
        </div>

        {isExpanded && (
          <div className={styles.groupContent}>
            {/* Subgroups */}
            {group.subgroups.map((subgroup) => renderSubgroup(group, subgroup))}

            {/* Direct prompts (without subgroup) */}
            {directPrompts.length > 0 && (
              <div className={styles.directPrompts}>
                {directPrompts.map((p) => renderPromptItem(p))}
              </div>
            )}

            {group.subgroups.length === 0 && directPrompts.length === 0 && (
              <div className={styles.empty}>Нет промптов</div>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={styles.tree}>
      <div className={styles.treeHeader}>
        <span className={styles.treeTitle}>Структура промптов</span>
      </div>
      <div className={styles.treeContent}>
        {groups.map(renderGroup)}
      </div>
    </div>
  )
}
