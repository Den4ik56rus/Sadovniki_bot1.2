/**
 * Главная страница редактора промптов.
 *
 * Двухколоночный layout:
 * - Левая колонка: дерево групп и промптов
 * - Правая колонка: редактор выбранного промпта
 */

import { useEffect } from 'react'
import { usePromptStore } from '@/store/promptStore'
import { getParam } from '@/router'
import { PromptGroupTree } from './PromptGroupTree'
import { PromptEditor } from './PromptEditor'
import styles from './PromptsPage.module.css'

export function PromptsPage() {
  const { fetchGroups, fetchPrompts, selectPrompt, isLoading, error, setError } = usePromptStore()

  useEffect(() => {
    // Загружаем группы и все промпты при монтировании
    const loadData = async () => {
      await fetchGroups()
      await fetchPrompts()

      // Restore selected prompt from URL
      const promptId = getParam('prompt')
      if (promptId) {
        selectPrompt(Number(promptId))
      }
    }
    loadData()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>Редактор промптов</h1>
        <p className={styles.subtitle}>
          Управление системными промптами для консультаций
        </p>
      </header>

      {error && (
        <div className={styles.errorBanner}>
          <span>{error}</span>
          <button onClick={() => setError(null)} className={styles.errorClose}>
            ×
          </button>
        </div>
      )}

      <div className={styles.content}>
        <aside className={styles.sidebar}>
          {isLoading ? (
            <div className={styles.loading}>Загрузка...</div>
          ) : (
            <PromptGroupTree />
          )}
        </aside>

        <main className={styles.editor}>
          <PromptEditor />
        </main>
      </div>
    </div>
  )
}
