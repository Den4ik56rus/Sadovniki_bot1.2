// Full Client Card Modal for Universal Funnels
import { useEffect, useState, useCallback } from 'react'
import type { CrmClientFull, ClientTag } from '@/types'
import { api } from '@/services/api'
import { LeftPanel } from '../crm/LeftPanel'
import { RightPanel } from '../crm/RightPanel'
import styles from './FunnelClientCardFull.module.css'

interface FunnelClientCardFullProps {
  clientId: number
  funnelId: string
  onClose: () => void
}

export function FunnelClientCardFull({ clientId, funnelId, onClose }: FunnelClientCardFullProps) {
  const [client, setClient] = useState<CrmClientFull | null>(null)
  const [allTags, setAllTags] = useState<ClientTag[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null)

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

  const handleUpdate = () => {
    fetchData()
  }

  const handleTopicClick = (topicId: number) => {
    setSelectedTopicId(topicId)
  }

  const handleBackToFeed = () => {
    setSelectedTopicId(null)
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
            />
          </div>
          <div className={styles.rightPanel}>
            <RightPanel
              clientId={clientId}
              onTaskUpdate={handleUpdate}
              selectedTopicId={selectedTopicId}
              onTopicClick={handleTopicClick}
              onBackToFeed={handleBackToFeed}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
