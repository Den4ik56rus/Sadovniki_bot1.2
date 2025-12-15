// Right Panel - Activity Feed
import { useState, useEffect, useCallback, useRef } from 'react'
import type { ActivityEvent, ClientTask, ActivityEventType } from '@/types'
import { api } from '@/services/api'
import { ActivityFilters } from './ActivityFilters'
import { ActivityItem } from './ActivityItem'
import { AddTaskModal } from './AddTaskModal'
import { AddNoteModal } from './AddNoteModal'
import styles from './RightPanel.module.css'

interface RightPanelProps {
  clientId: number
  onTaskUpdate?: () => void
}

const ALL_EVENT_TYPES: ActivityEventType[] = [
  'consultation',
  'task_created',
  'task_completed',
  'note',
  'status_change',
  'tag_change',
]

export function RightPanel({ clientId, onTaskUpdate }: RightPanelProps) {
  const [activity, setActivity] = useState<ActivityEvent[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [activeFilters, setActiveFilters] = useState<ActivityEventType[]>(ALL_EVENT_TYPES)
  const [showAddTask, setShowAddTask] = useState(false)
  const [showAddNote, setShowAddNote] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = useCallback(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [])

  const fetchActivity = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await api.getClientActivity(clientId, {
        types: activeFilters.length === ALL_EVENT_TYPES.length ? undefined : activeFilters,
        limit: 100,
      })
      // Reverse to show oldest first, newest at bottom
      setActivity(data.reverse())
    } catch (e) {
      console.error('Failed to fetch activity:', e)
    } finally {
      setIsLoading(false)
    }
  }, [clientId, activeFilters])

  useEffect(() => {
    fetchActivity()
  }, [fetchActivity])

  // Scroll to bottom after activity loads
  useEffect(() => {
    if (!isLoading && activity.length > 0) {
      scrollToBottom()
    }
  }, [isLoading, activity.length, scrollToBottom])

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

  return (
    <div className={styles.panel}>
      {/* Header with filters */}
      <div className={styles.header}>
        <h3 className={styles.title}>Лента активности</h3>
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
