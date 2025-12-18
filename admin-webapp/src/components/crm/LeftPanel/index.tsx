// Left Panel - Client info with tabs (i2crm style)
import { useState, useEffect, useCallback } from 'react'
import type {
  CrmClientFull,
  ClientPriority,
  ClientTag,
  ClientNote,
  FunnelStage,
} from '@/types'
import { api } from '@/services/api'
import { useCurrencyStore } from '@/store'
import { useFunnelStore } from '@/store/funnelStore'
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
  pending_payment: '#F59E0B',
  active_subscription: '#22C55E',
  churned: '#EF4444',
}

interface LeftPanelProps {
  client: CrmClientFull
  allTags: ClientTag[]
  funnelId?: string // Current funnel ID
  onUpdate: () => void
  onTopicClick?: (topicId: number) => void
  onClose?: () => void
}

export function LeftPanel({ client, allTags, funnelId, onUpdate, onTopicClick, onClose }: LeftPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>('main')
  const [isUpdating, setIsUpdating] = useState(false)
  const [notes, setNotes] = useState<ClientNote[]>([])
  const [selectedFunnelId, setSelectedFunnelId] = useState<string>(funnelId || '')
  const [funnelStages, setFunnelStages] = useState<FunnelStage[]>([])
  const { usdRate } = useCurrencyStore()
  const { funnels, fetchFunnels, stages: currentFunnelStages } = useFunnelStore()

  // Set initial funnel ID from props
  useEffect(() => {
    if (funnelId && !selectedFunnelId) {
      setSelectedFunnelId(funnelId)
    }
  }, [funnelId, selectedFunnelId])

  // Fetch funnels on mount
  useEffect(() => {
    if (funnels.length === 0) {
      fetchFunnels()
    }
  }, [funnels.length, fetchFunnels])

  // Fetch stages for selected funnel
  useEffect(() => {
    const loadStages = async () => {
      if (!selectedFunnelId) return

      // If selected funnel is the current one, use stages from store
      if (selectedFunnelId === funnelId) {
        setFunnelStages(currentFunnelStages)
      } else {
        // Otherwise fetch stages for the selected funnel
        try {
          const response = await api.getFunnelStages(selectedFunnelId)
          setFunnelStages(response.stages)
        } catch (error) {
          console.error('Failed to fetch funnel stages:', error)
          setFunnelStages([])
        }
      }
    }
    loadStages()
  }, [selectedFunnelId, funnelId, currentFunnelStages])

  const currentStatus = client.status || 'new'
  const currentStage = funnelStages.find(s => s.stage_key === currentStatus)
  const statusColor = currentStage?.color || DEFAULT_STATUS_COLORS[currentStatus] || '#6B7280'
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

  // Handle funnel change - transfer client to new funnel
  const handleFunnelChange = async (newFunnelId: string) => {
    if (newFunnelId === funnelId || isUpdating || !funnelId) return

    setSelectedFunnelId(newFunnelId)
    // Don't transfer yet - wait for status selection
  }

  // Handle status change within funnel or transfer to new funnel
  const handleStatusChange = async (newStageKey: string) => {
    if (isUpdating) return

    setIsUpdating(true)
    try {
      if (selectedFunnelId !== funnelId && funnelId) {
        // Transfer to new funnel with selected status
        await api.transferClient(funnelId, client.id, selectedFunnelId, newStageKey)
      } else if (newStageKey !== client.status && funnelId) {
        // Move within same funnel
        await api.moveClientStage(funnelId, client.id, newStageKey)
      }
      onUpdate()
    } catch (e) {
      console.error('Failed to update status:', e)
      // Reset funnel selection on error
      setSelectedFunnelId(funnelId || '')
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

        {/* Two-step funnel/status selection */}
        <div className={styles.funnelSelectors}>
          {/* Funnel selector */}
          <div className={styles.selectorGroup}>
            <label className={styles.selectorLabel}>Воронка</label>
            <select
              className={styles.funnelSelect}
              value={selectedFunnelId}
              onChange={(e) => handleFunnelChange(e.target.value)}
              disabled={isUpdating}
            >
              {funnels.map((funnel) => (
                <option key={funnel.id} value={funnel.id}>{funnel.title}</option>
              ))}
            </select>
          </div>

          {/* Status selector */}
          <div className={styles.selectorGroup}>
            <label className={styles.selectorLabel}>Статус</label>
            <select
              className={styles.statusSelect}
              value={selectedFunnelId === funnelId ? client.status : ''}
              onChange={(e) => handleStatusChange(e.target.value)}
              disabled={isUpdating || funnelStages.length === 0}
              style={{ backgroundColor: statusColor, color: 'white' }}
            >
              {selectedFunnelId !== funnelId && (
                <option value="">Выберите статус...</option>
              )}
              {funnelStages.map((stage) => (
                <option key={stage.stage_key} value={stage.stage_key}>{stage.title}</option>
              ))}
            </select>
          </div>
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
