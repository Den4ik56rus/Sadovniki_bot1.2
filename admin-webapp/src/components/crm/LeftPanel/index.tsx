// Left Panel - Client info and fields
import { useState } from 'react'
import type {
  CrmClientFull,
  ClientPriority,
  FunnelStatus,
  ClientTag,
  CustomFieldValue,
} from '@/types'
import { api } from '@/services/api'
import { useCurrencyStore } from '@/store'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import { TagsSection } from './TagsSection'
import { CustomFieldsSection } from './CustomFieldsSection'
import styles from './LeftPanel.module.css'

interface LeftPanelProps {
  client: CrmClientFull
  allTags: ClientTag[]
  onUpdate: () => void
}

const STATUS_LABELS: Record<FunnelStatus, string> = {
  new: 'Новый',
  tried: 'Попробовал',
  trial_ended: 'Закончился триал',
  paid: 'Купил',
}

const PRIORITY_LABELS: Record<ClientPriority, string> = {
  low: 'Низкий',
  normal: 'Обычный',
  high: 'Высокий',
  vip: 'VIP',
}

const PRIORITY_COLORS: Record<ClientPriority, string> = {
  low: '#9CA3AF',
  normal: '#6B7280',
  high: '#F59E0B',
  vip: '#FFD700',
}

export function LeftPanel({ client, allTags, onUpdate }: LeftPanelProps) {
  const { usdRate } = useCurrencyStore()
  const [isUpdating, setIsUpdating] = useState(false)

  const displayName = client.first_name || client.username || `User ${client.telegram_user_id}`

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    try {
      return format(new Date(dateStr), 'd MMM yyyy', { locale: ru })
    } catch {
      return '-'
    }
  }

  const formatCost = (costUsd: number) => {
    const costRub = costUsd * usdRate
    if (costRub < 1) {
      return `${Math.round(costRub * 100)} коп.`
    }
    return `${costRub.toFixed(0)} ₽`
  }

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

  return (
    <div className={styles.panel}>
      {/* Header with avatar */}
      <div className={styles.header}>
        <div className={styles.avatar}>
          {displayName.charAt(0).toUpperCase()}
        </div>
        <div className={styles.headerInfo}>
          <h3 className={styles.name}>{displayName}</h3>
          {client.username && (
            <span className={styles.username}>@{client.username}</span>
          )}
        </div>
      </div>

      {/* Stats row */}
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

      {/* Base fields */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Основная информация</h4>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Telegram ID</span>
          <span className={styles.fieldValue}>{client.telegram_user_id}</span>
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Регион</span>
          <span className={styles.fieldValue}>{client.region || '-'}</span>
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>С нами с</span>
          <span className={styles.fieldValue}>{formatDate(client.user_created_at)}</span>
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Последняя активность</span>
          <span className={styles.fieldValue}>{formatDate(client.last_consultation_at)}</span>
        </div>
      </div>

      {/* Status fields */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Статус</h4>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Воронка</span>
          <select
            className={styles.select}
            value={client.status}
            onChange={(e) => handleStatusChange(e.target.value as FunnelStatus)}
            disabled={isUpdating}
          >
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Приоритет</span>
          <select
            className={styles.select}
            value={client.priority}
            onChange={(e) => handlePriorityChange(e.target.value as ClientPriority)}
            disabled={isUpdating}
            style={{ color: PRIORITY_COLORS[client.priority] }}
          >
            {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Источник</span>
          <input
            type="text"
            className={styles.input}
            value={client.source || ''}
            placeholder="Откуда пришёл"
            onChange={(e) => handleSourceChange(e.target.value)}
            disabled={isUpdating}
          />
        </div>
      </div>

      {/* Tags */}
      <TagsSection
        clientTags={client.tags}
        allTags={allTags}
        onChange={handleTagsChange}
      />

      {/* Custom fields */}
      <CustomFieldsSection
        fields={client.custom_fields}
        clientId={client.id}
        onChange={handleFieldsChange}
      />
    </div>
  )
}
