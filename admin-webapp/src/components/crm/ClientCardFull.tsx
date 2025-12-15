// Full Client Card Modal - Two-panel layout
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

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  if (isLoading || !client) {
    return (
      <div className={styles.backdrop} onClick={handleBackdropClick}>
        <div className={styles.modal}>
          <div className={styles.loading}>Загрузка...</div>
        </div>
      </div>
    )
  }

  const displayName = client.first_name || client.username || `User ${client.telegram_user_id}`

  return (
    <div className={styles.backdrop} onClick={handleBackdropClick}>
      <div className={styles.modal}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerTitle}>
            <span className={styles.clientId}>#{client.id}</span>
            <h2 className={styles.name}>{displayName}</h2>
            {client.username && (
              <span className={styles.username}>@{client.username}</span>
            )}
          </div>
          <button className={styles.closeBtn} onClick={onClose}>
            ✕
          </button>
        </div>

        {/* Two-panel layout */}
        <div className={styles.content}>
          <div className={styles.leftPanel}>
            <LeftPanel
              client={client}
              allTags={allTags}
              onUpdate={handleUpdate}
            />
          </div>
          <div className={styles.rightPanel}>
            <RightPanel
              clientId={clientId}
              onTaskUpdate={handleUpdate}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
