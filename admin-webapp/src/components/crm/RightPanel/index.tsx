// Right Panel - Activity Feed with Topic View, Article View, and Chat Messages
import { useState, useEffect, useCallback, useRef } from 'react'
import type { ActivityEvent, ActivityEventType, Message } from '@/types'
import { api } from '@/services/api'
import { ActivityFilters } from './ActivityFilters'
import { ActivityItem } from './ActivityItem'
import { AddTaskModal } from './AddTaskModal'
import { AddNoteModal } from './AddNoteModal'
import { TopicView } from './TopicView'
import { ArticleView } from './ArticleView'
import styles from './RightPanel.module.css'

interface RightPanelProps {
  clientId: number
  onTaskUpdate?: () => void
  selectedTopicId?: number | null
  onTopicClick?: (topicId: number) => void
  selectedArticleId?: number | null
  onArticleClick?: (articleId: number) => void
  onBackToFeed?: () => void
  sseRefreshKey?: number
  sseNewMessages?: Message[]
}

const ALL_EVENT_TYPES: ActivityEventType[] = [
  'chat_message',
  'consultation',
  'article',
  'task_created',
  'task_completed',
  'note',
  'status_change',
  'tag_change',
]

export function RightPanel({
  clientId,
  onTaskUpdate,
  selectedTopicId,
  onTopicClick,
  selectedArticleId,
  onArticleClick,
  onBackToFeed,
  sseRefreshKey,
  // sseNewMessages available via props for ChatHistory integration
}: RightPanelProps) {
  const [activity, setActivity] = useState<ActivityEvent[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeFilters, setActiveFilters] = useState<ActivityEventType[]>(ALL_EVENT_TYPES)
  const [showAddTask, setShowAddTask] = useState(false)
  const [showAddNote, setShowAddNote] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  const scrollToBottom = useCallback(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [])

  const fetchActivity = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.getClientActivity(clientId, {
        types: activeFilters.length === ALL_EVENT_TYPES.length ? undefined : activeFilters,
        limit: 500,
      })
      // Reverse to show oldest first, newest at bottom
      setActivity(data.reverse())
    } catch (e) {
      console.error('Failed to fetch activity:', e)
      setError(String(e))
    } finally {
      setIsLoading(false)
    }
  }, [clientId, activeFilters])

  // Silent refetch without loading spinner (for SSE updates)
  const silentRefetchActivity = useCallback(async () => {
    try {
      const data = await api.getClientActivity(clientId, {
        types: activeFilters.length === ALL_EVENT_TYPES.length ? undefined : activeFilters,
        limit: 500,
      })
      setActivity(data.reverse())
      // Auto-scroll to bottom after new data
      requestAnimationFrame(() => scrollToBottom())
    } catch (e) {
      console.error('Failed to silently refetch activity:', e)
    }
  }, [clientId, activeFilters, scrollToBottom])

  useEffect(() => {
    fetchActivity()
  }, [fetchActivity])

  // SSE: debounced activity refetch when sseRefreshKey changes
  useEffect(() => {
    if (sseRefreshKey && sseRefreshKey > 0) {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        silentRefetchActivity()
      }, 500)
    }
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [sseRefreshKey, silentRefetchActivity])

  // Scroll to bottom after activity loads or when returning from TopicView/ArticleView
  useEffect(() => {
    if (!isLoading && activity.length > 0 && !selectedTopicId && !selectedArticleId) {
      requestAnimationFrame(() => scrollToBottom())
    }
  }, [isLoading, activity.length, selectedTopicId, selectedArticleId, scrollToBottom])

  const handleFilterChange = (filters: ActivityEventType[]) => {
    setActiveFilters(filters)
  }

  const handleTaskCreated = async (data: { title: string; description?: string; due_date?: string; priority?: string }) => {
    try {
      await api.createTask(clientId, {
        title: data.title,
        description: data.description,
        due_date: data.due_date,
        priority: data.priority as 'low' | 'medium' | 'high',
      })
      setShowAddTask(false)
      fetchActivity()
      onTaskUpdate?.()
    } catch (e) {
      console.error('Failed to create task:', e)
    }
  }

  const handleNoteCreated = async (text: string) => {
    try {
      await api.createNote(clientId, { text })
      setShowAddNote(false)
      fetchActivity()
    } catch (e) {
      console.error('Failed to create note:', e)
    }
  }

  const handleTaskComplete = async (taskId: number) => {
    try {
      await api.completeTask(taskId)
      fetchActivity()
      onTaskUpdate?.()
    } catch (e) {
      console.error('Failed to complete task:', e)
    }
  }

  const handleTaskDelete = async (taskId: number) => {
    try {
      await api.deleteTask(taskId)
      fetchActivity()
      onTaskUpdate?.()
    } catch (e) {
      console.error('Failed to delete task:', e)
    }
  }

  const handleNoteDelete = async (noteId: number) => {
    try {
      await api.deleteNote(noteId)
      fetchActivity()
    } catch (e) {
      console.error('Failed to delete note:', e)
    }
  }

  // Show TopicView if a topic is selected
  if (selectedTopicId && onBackToFeed) {
    return (
      <TopicView
        topicId={selectedTopicId}
        onBack={onBackToFeed}
      />
    )
  }

  // Show ArticleView if an article is selected
  if (selectedArticleId && onBackToFeed) {
    return (
      <ArticleView
        articleId={selectedArticleId}
        onBack={onBackToFeed}
      />
    )
  }

  return (
    <div className={styles.panel}>
      {/* Header with filters */}
      <div className={styles.header}>
        <ActivityFilters
          activeFilters={activeFilters}
          allFilters={ALL_EVENT_TYPES}
          onChange={handleFilterChange}
        />
      </div>

      {/* Activity list */}
      <div className={styles.activityList} ref={listRef}>
        {isLoading ? (
          <div className={styles.loading}>Загрузка...</div>
        ) : error ? (
          <div className={styles.empty}>
            <div>Ошибка загрузки</div>
            <button className={styles.addBtn} onClick={fetchActivity} style={{ marginTop: 8 }}>
              Повторить
            </button>
          </div>
        ) : activity.length === 0 ? (
          <div className={styles.empty}>Нет активности</div>
        ) : (
          activity.map(event => (
            <ActivityItem
              key={`${event.source || 'activity'}-${event.id}`}
              event={event}
              onTaskComplete={handleTaskComplete}
              onTaskDelete={handleTaskDelete}
              onNoteDelete={handleNoteDelete}
              onTopicClick={onTopicClick}
              onArticleClick={onArticleClick}
            />
          ))
        )}
      </div>

      {/* Action buttons */}
      <div className={styles.actions}>
        <button
          className={styles.addBtn}
          onClick={() => setShowAddTask(true)}
        >
          + Задача
        </button>
        <button
          className={styles.addBtn}
          onClick={() => setShowAddNote(true)}
        >
          + Заметка
        </button>
      </div>

      {/* Modals */}
      {showAddTask && (
        <AddTaskModal
          onSubmit={handleTaskCreated}
          onClose={() => setShowAddTask(false)}
        />
      )}

      {showAddNote && (
        <AddNoteModal
          onSubmit={handleNoteCreated}
          onClose={() => setShowAddNote(false)}
        />
      )}
    </div>
  )
}
