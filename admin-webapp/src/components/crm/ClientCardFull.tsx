// Full Client Card Modal - Full Screen Layout (i2crm inspired)
import { useEffect, useState, useCallback } from 'react'
import type { CrmClientFull, ClientTag, Message } from '@/types'
import { api } from '@/services/api'
import { useSSE } from '@/hooks/useSSE'
import { LeftPanel } from './LeftPanel'
import { RightPanel } from './RightPanel'
import styles from './ClientCardFull.module.css'

interface ClientCardFullProps {
  clientId: number
  onClose: () => void
}

export function ClientCardFull({ clientId, onClose }: ClientCardFullProps) {
  const [client, setClient] = useState<CrmClientFull | null>(null)
  const [allTags, setAllTags] = useState<ClientTag[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null)
  const [selectedArticleId, setSelectedArticleId] = useState<number | null>(null)

  // SSE state for real-time updates
  const [sseRefreshKey, setSseRefreshKey] = useState(0)
  const [sseNewMessages, setSseNewMessages] = useState<Message[]>([])

  const fetchData = useCallback(async () => {
    try {
      const [clientData, tagsData] = await Promise.all([
        api.getClientFull(clientId),
        api.getTags(),
      ])
      setClient(clientData)
      setAllTags(tagsData)
    } catch (error) {
      console.error('Failed to fetch client:', error)
    } finally {
      setIsLoading(false)
    }
  }, [clientId])

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
        // Append new message for ChatHistory
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
    setSelectedArticleId(null)
  }

  const handleArticleClick = (articleId: number) => {
    setSelectedArticleId(articleId)
    setSelectedTopicId(null)
  }

  const handleBackToFeed = () => {
    setSelectedTopicId(null)
    setSelectedArticleId(null)
  }

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (selectedTopicId || selectedArticleId) {
          setSelectedTopicId(null)
          setSelectedArticleId(null)
        } else {
          onClose()
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose, selectedTopicId, selectedArticleId])

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
        {/* Two-panel layout - no header, close button in LeftPanel */}
        <div className={styles.content}>
          <div className={styles.leftPanel}>
            <LeftPanel
              client={client}
              allTags={allTags}
              onUpdate={handleUpdate}
              onTopicClick={handleTopicClick}
              onClose={onClose}
            />
          </div>
          <div className={styles.rightPanel}>
            <RightPanel
              clientId={clientId}
              onTaskUpdate={handleUpdate}
              selectedTopicId={selectedTopicId}
              onTopicClick={handleTopicClick}
              selectedArticleId={selectedArticleId}
              onArticleClick={handleArticleClick}
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
