/**
 * Дерево групп и подгрупп промптов.
 *
 * Отображает иерархию:
 * - Группа (раскрывающаяся)
 *   - Подгруппа (раскрывающаяся)
 *     - Промпт (кликабельный)
 *   - Промпт без подгруппы
 */

import { usePromptStore } from '@/store/promptStore'
import type { PromptGroup, PromptSubgroup, Prompt } from '@/types'
import styles from './PromptGroupTree.module.css'

export function PromptGroupTree() {
  const {
    groups,
    prompts,
    selectedPrompt,
    expandedGroups,
    expandedSubgroups,
    toggleGroupExpanded,
    toggleSubgroupExpanded,
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

  const handlePromptClick = (prompt: Prompt) => {
    selectPrompt(prompt.id)
  }

  const handleToggleEnabled = (e: React.MouseEvent, prompt: Prompt) => {
    e.stopPropagation()
    togglePromptEnabled(prompt.id, !prompt.is_enabled)
  }

  const renderPromptItem = (prompt: Prompt) => {
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
        <span className={styles.promptName}>{prompt.name}</span>
        {prompt.is_system && (
          <span className={styles.systemBadge} title="Системный промпт">
            S
          </span>
        )}
      </div>
    )
  }

  const renderSubgroup = (group: PromptGroup, subgroup: PromptSubgroup) => {
    const key = `${group.id}-${subgroup.id}`
    const isExpanded = expandedSubgroups.has(key)
    const subgroupPrompts = getPromptsForSubgroup(group.id, subgroup.id)

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
            {subgroupPrompts.map(renderPromptItem)}
            {subgroupPrompts.length === 0 && (
              <div className={styles.empty}>Нет промптов</div>
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
                {directPrompts.map(renderPromptItem)}
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
