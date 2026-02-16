// Main Tab - Basic client info, status fields, tags (no hero section)
import type {
  CrmClientFull,
  ClientPriority,
  ClientTag,
} from '@/types'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import { TagsSection } from './TagsSection'
import styles from './MainTab.module.css'

interface MainTabProps {
  client: CrmClientFull
  allTags: ClientTag[]
  isUpdating: boolean
  onPriorityChange: (priority: ClientPriority) => void
  onSourceChange: (source: string) => void
  onTagsChange: (tagIds: number[]) => void
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

export function MainTab({
  client,
  allTags,
  isUpdating,
  onPriorityChange,
  onSourceChange,
  onTagsChange,
}: MainTabProps) {
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    try {
      return format(new Date(dateStr), 'd MMM yyyy', { locale: ru })
    } catch {
      return '-'
    }
  }

  return (
    <div className={styles.content}>
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

      {/* Status fields - without funnel selector */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Статус</h4>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Приоритет</span>
          <select
            className={styles.select}
            value={client.priority}
            onChange={(e) => onPriorityChange(e.target.value as ClientPriority)}
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
            onChange={(e) => onSourceChange(e.target.value)}
            disabled={isUpdating}
          />
        </div>
      </div>

      {/* Referral Program */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Реферальная программа</h4>

        {client.referrer && (
          <div className={styles.field}>
            <span className={styles.fieldLabel}>Приглашён</span>
            <span className={styles.fieldValue}>
              {client.referrer.first_name || client.referrer.username || `#${client.referrer.id}`}
            </span>
          </div>
        )}

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Реф. код</span>
          <span className={styles.fieldValue}>
            {client.referral_code
              ? <code className={styles.referralCode}>{client.referral_code}</code>
              : '-'}
          </span>
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Приглашено</span>
          <span className={styles.fieldValue}>{client.referrals_count ?? 0}</span>
        </div>
      </div>

      {/* Tags */}
      <TagsSection
        clientTags={client.tags}
        allTags={allTags}
        onChange={onTagsChange}
      />
    </div>
  )
}
