// Full Client Card Modal for Universal Funnels
import { useEffect, useState, useCallback } from 'react'
import type { CrmClientFull, ClientTag, Message } from '@/types'
import { api } from '@/services/api'
import { useSSE } from '@/hooks/useSSE'
import { navigate as routerNavigate, matchRoute } from '@/router'
import { useUIStore } from '@/store'
import { LeftPanel } from '../crm/LeftPanel'
import { RightPanel } from '../crm/RightPanel'
import styles from './FunnelClientCardFull.module.css'

interface FunnelClientCardFullProps {
  clientId: number
  funnelId: string
  onClose: () => void
}

export function FunnelClientCardFull({ clientId, funnelId, onClose }: FunnelClientCardFullProps) {
  const { currentView } = useUIStore()
  const [client, setClient] = useState<CrmClientFull | null>(null)
  const [allTags, setAllTags] = useState<ClientTag[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // SSE state for real-time updates
  const [sseRefreshKey, setSseRefreshKey] = useState(0)
  const [sseNewMessages, setSseNewMessages] = useState<Message[]>([])

  // Read initial topicId from URL
  const [selectedTopicId, setSelectedTopicIdRaw] = useState<number | null>(() => {
    const match = matchRoute()
    return match.topicId ?? null
  })

  // Wrapper that syncs topicId to URL
  const setSelectedTopicId = useCallback((topicId: number | null) => {
    setSelectedTopicIdRaw(topicId)
    if (topicId) {
      routerNavigate({ view: currentView, funnelId, clientId, topicId })
    } else {
      routerNavigate({ view: currentView, funnelId, clientId }, { replace: true })
    }
  }, [currentView, funnelId, clientId])

  const fetchData = useCallback(async () => {
    try {
      const [clientData, tagsData] = await Promise.all([
        api.getClientFull(clientId, funnelId),
        api.getTags(),
      ])
      setClient(clientData)
      setAllTags(tagsData)
    } catch (error) {
      console.error('Failed to fetch client:', error)
    } finally {
      setIsLoading(false)
    }
  }, [clientId, funnelId])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Reset SSE state when clientId changes
  useEffect(() => {
    setSseRefreshKey(0)
    setSseNewMessages([])
  }, [clientId])

  // SSE: subscribe to client events
  const handleClientSSE = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data)

      if (event.type === 'heartbeat') return

      if (event.type === 'new_message') {
        setSseNewMessages(prev => {
          if (prev.some(m => m.id === data.id)) return prev
          return [...prev, data as Message]
        })
      }

      // Trigger activity feed refetch for any event
      setSseRefreshKey(k => k + 1)
    } catch (e) {
      console.error('[SSE Client] Failed to parse event:', e)
    }
  }, [])

  useSSE({
    endpoint: api.sse.clientEvents(clientId),
    onMessage: handleClientSSE,
    enabled: !isLoading,
    eventTypes: ['new_message', 'new_consultation', 'new_topic', 'heartbeat'],
  })

  const handleUpdate = () => {
    fetchData()
  }

  const handleTopicClick = (topicId: number) => {
    setSelectedTopicId(topicId)
  }

  const handleBackToFeed = () => {
    setSelectedTopicId(null)
  }

  const handleDelete = async () => {
    if (!client) return
    const name = client.first_name || client.username || `ID ${client.telegram_user_id}`
    if (!window.confirm(`Удалить пользователя ${name}?\n\nВсе данные будут удалены безвозвратно. При следующем /start он будет как новый.`)) return
    try {
      await api.deleteClient(clientId)
      onClose()
    } catch (error) {
      console.error('Failed to delete client:', error)
      alert('Ошибка при удалении пользователя')
    }
  }

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (selectedTopicId) {
          setSelectedTopicId(null)
        } else {
          onClose()
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose, selectedTopicId])

  if (isLoading || !client) {
    return (
      <div className={styles.backdrop}>
        <div className={styles.modal}>
          <div className={styles.loading}>Загрузка...</div>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.backdrop}>
      <div className={styles.modal}>
        {/* Two-panel layout */}
        <div className={styles.content}>
          <div className={styles.leftPanel}>
            <LeftPanel
              client={client}
              allTags={allTags}
              funnelId={funnelId}
              onUpdate={handleUpdate}
              onTopicClick={handleTopicClick}
              onClose={onClose}
              onDelete={handleDelete}
            />
          </div>
          <div className={styles.rightPanel}>
            <RightPanel
              clientId={clientId}
              onTaskUpdate={handleUpdate}
              selectedTopicId={selectedTopicId}
              onTopicClick={handleTopicClick}
              onBackToFeed={handleBackToFeed}
              sseRefreshKey={sseRefreshKey}
              sseNewMessages={sseNewMessages}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
