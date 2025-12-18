// Full Client Card Modal - Full Screen Layout (i2crm inspired)
import { useEffect, useState, useCallback } from 'react'
import type { CrmClientFull, ClientTag } from '@/types'
import { api } from '@/services/api'
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
            />
          </div>
        </div>
      </div>
    </div>
  )
}
