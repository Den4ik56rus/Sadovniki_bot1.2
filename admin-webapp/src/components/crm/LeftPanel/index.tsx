// Left Panel - Client info with tabs (i2crm style)
import { useState, useEffect, useCallback } from 'react'
import type {
  CrmClientFull,
  ClientPriority,
  FunnelStatus,
  ClientTag,
  ClientNote,
} from '@/types'
import { api } from '@/services/api'
import { useCurrencyStore, useCrmStore } from '@/store'
import { TabsNav, type TabId } from './TabsNav'
import { MainTab } from './MainTab'
import { AdditionalTab } from './AdditionalTab'
import { BillingTab } from './BillingTab'
import styles from './LeftPanel.module.css'

const DEFAULT_STATUS_COLORS: Record<string, string> = {
  new: '#3B82F6',
  tried: '#8B5CF6',
  trial_ended: '#F59E0B',
  paid: '#22C55E',
}

interface LeftPanelProps {
  client: CrmClientFull
  allTags: ClientTag[]
  onUpdate: () => void
  onTopicClick?: (topicId: number) => void
  onClose?: () => void
}

export function LeftPanel({ client, allTags, onUpdate, onTopicClick, onClose }: LeftPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>('main')
  const [isUpdating, setIsUpdating] = useState(false)
  const [notes, setNotes] = useState<ClientNote[]>([])
  const { usdRate } = useCurrencyStore()
  const { columnConfigs } = useCrmStore()

  const currentStatus = client.status || 'new'
  const columnConfig = columnConfigs.find(c => c.id === currentStatus)
  const statusColor = columnConfig?.color || DEFAULT_STATUS_COLORS[currentStatus] || '#6B7280'
  const displayName = client.first_name || client.username || `User ${client.telegram_user_id}`

  const formatCost = (costUsd: number) => {
    const costRub = costUsd * usdRate
    if (costRub < 1) {
      return `${Math.round(costRub * 100)} коп.`
    }
    return `${costRub.toFixed(0)} ₽`
  }

  // Fetch notes for AdditionalTab
  const fetchNotes = useCallback(async () => {
    try {
      const data = await api.getClientNotes(client.id)
      setNotes(data)
    } catch (e) {
      console.error('Failed to fetch notes:', e)
    }
  }, [client.id])

  useEffect(() => {
    fetchNotes()
  }, [fetchNotes])

  const handleStatusChange = async (newStatus: FunnelStatus) => {
    if (newStatus === client.status || isUpdating) return
    setIsUpdating(true)
    try {
      await api.updateClientStatus(client.id, newStatus)
      onUpdate()
    } catch (e) {
      console.error('Failed to update status:', e)
    } finally {
      setIsUpdating(false)
    }
  }

  const handlePriorityChange = async (newPriority: ClientPriority) => {
    if (newPriority === client.priority || isUpdating) return
    setIsUpdating(true)
    try {
      await api.updateClientPriority(client.id, newPriority)
      onUpdate()
    } catch (e) {
      console.error('Failed to update priority:', e)
    } finally {
      setIsUpdating(false)
    }
  }

  const handleSourceChange = async (newSource: string) => {
    if (isUpdating) return
    setIsUpdating(true)
    try {
      await api.updateClientSource(client.id, newSource)
      onUpdate()
    } catch (e) {
      console.error('Failed to update source:', e)
    } finally {
      setIsUpdating(false)
    }
  }

  const handleTagsChange = async (tagIds: number[]) => {
    try {
      await api.updateClientTags(client.id, tagIds)
      onUpdate()
    } catch (e) {
      console.error('Failed to update tags:', e)
    }
  }

  const handleFieldsChange = async (fields: Record<number, unknown>) => {
    try {
      await api.updateClientFieldValues(client.id, fields)
      onUpdate()
    } catch (e) {
      console.error('Failed to update fields:', e)
    }
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'main':
        return (
          <MainTab
            client={client}
            allTags={allTags}
            isUpdating={isUpdating}
            onPriorityChange={handlePriorityChange}
            onSourceChange={handleSourceChange}
            onTagsChange={handleTagsChange}
          />
        )
      case 'additional':
        return (
          <AdditionalTab
            fields={client.custom_fields}
            notes={notes}
            clientId={client.id}
            onFieldsChange={handleFieldsChange}
          />
        )
      case 'billing':
        return (
          <BillingTab
            clientId={client.id}
            totalCostUsd={client.total_cost_usd}
            totalConsultations={client.total_consultations}
            onTopicClick={onTopicClick}
          />
        )
      default:
        return null
    }
  }

  return (
    <div className={styles.panel}>
      {/* Header - i2crm style */}
      <div className={styles.header}>
        <div className={styles.headerTop}>
          {onClose && (
            <button className={styles.backBtn} onClick={onClose} title="Назад к воронке">
              ‹
            </button>
          )}
          <span className={styles.dealTitle}>Сделка #{client.id}</span>
          <button className={styles.menuBtn} title="Меню">⋯</button>
        </div>

        <div className={styles.tagRow}>
          <button className={styles.tagButton}>#ТЕГИРОВАТЬ</button>
        </div>

        <div className={styles.clientInfo}>
          <span className={styles.clientSource}>от: Telegram</span>
          <h3 className={styles.clientName}>{displayName}</h3>
        </div>

        <div className={styles.funnelRow}>
          <select
            className={styles.funnelSelect}
            value={client.status}
            onChange={(e) => handleStatusChange(e.target.value as FunnelStatus)}
            disabled={isUpdating}
            style={{ backgroundColor: statusColor, color: 'white' }}
          >
            {columnConfigs.map((config) => (
              <option key={config.id} value={config.id}>{config.title}</option>
            ))}
          </select>
        </div>

        <div className={styles.statsRow}>
          <div className={styles.stat}>
            <span className={styles.statValue}>{client.total_consultations}</span>
            <span className={styles.statLabel}>консультаций</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statValue}>0 ₽</span>
            <span className={styles.statLabel}>оплатил</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statValue}>{formatCost(client.total_cost_usd)}</span>
            <span className={styles.statLabel}>потрачено</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <TabsNav activeTab={activeTab} onChange={setActiveTab} />

      {/* Tab content */}
      <div className={styles.tabContent}>
        {renderTabContent()}
      </div>
    </div>
  )
}
